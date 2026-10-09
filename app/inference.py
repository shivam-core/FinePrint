# app/inference.py
import joblib
import numpy as np
import regex as re
from app.categories import get_category_context, CATEGORY_MAPPING

class ModelManager:
    def __init__(self, model_path="artifacts/model.joblib"):
        self.model_data = joblib.load(model_path)
        self.vectorizer = self.model_data["vectorizer"]
        self.classifier = self.model_data["classifier"]
        self.thresholds = self.model_data["thresholds"]
        
        # Pre-extract vocabulary and coefficients for explanations
        self.vocab = self.vectorizer.vocabulary_
        self.reverse_vocab = {v: k for k, v in self.vocab.items()}
        # For each class, get the coefficients
        self.coefs = []
        self.intercepts = []
        for i in range(8):
            self.coefs.append(self.classifier.estimators_[i].coef_[0])
            self.intercepts.append(self.classifier.estimators_[i].intercept_[0])

    def clean_text(self, text):
        return re.sub(r'\s+', ' ', text).strip()

    def count_words(self, text):
        return len(re.findall(r"\b\w+\b", text))

    def analyze_segment(self, segment_id, text, start, end, page=None):
        clean_t = self.clean_text(text)
        word_count = self.count_words(clean_t)
        
        # Check <=2 word heuristic
        if word_count <= 2:
            return {
                "id": segment_id,
                "text": text,
                "start": start,
                "end": end,
                "page": page,
                "status": "needs_review",
                "reason": "insufficient_text",
                "categories": [],
                "scores": {},
                "explanations": {}
            }
            
        X = self.vectorizer.transform([clean_t])
        # Find if OOV
        if X.nnz == 0:
            return {
                "id": segment_id,
                "text": text,
                "start": start,
                "end": end,
                "page": page,
                "status": "needs_review",
                "reason": "all_oov",
                "categories": [],
                "scores": {},
                "explanations": {}
            }
            
        probs = self.classifier.predict_proba(X)[0]
        
        categories = []
        scores = {}
        explanations = {}
        status = "no_issue_detected"
        
        active_features_indices = X.nonzero()[1]
        active_features_tfidf = X.data
        
        for i in range(8):
            score = float(probs[i])
            scores[str(i)] = score
            threshold = float(self.thresholds[i])
            
            if score >= threshold:
                status = "potentially_unfair"
                categories.append({
                    "id": i,
                    "name": CATEGORY_MAPPING[i],
                    "model_score": score,
                    "threshold": threshold
                })
                
                # Generate explanation
                coef = self.coefs[i]
                intercept = float(self.intercepts[i])
                
                contributions = []
                for idx, tfidf_val in zip(active_features_indices, active_features_tfidf):
                    c = coef[idx] * tfidf_val
                    if abs(c) > 0.001:  # Only care about non-trivial contributions
                        feature_name = self.reverse_vocab[idx]
                        contributions.append({
                            "feature": feature_name,
                            "weight": float(c),
                        })
                        
                # Sort by absolute weight to find top positive and negative
                pos_contributions = sorted([c for c in contributions if c["weight"] > 0], key=lambda x: x["weight"], reverse=True)[:5]
                neg_contributions = sorted([c for c in contributions if c["weight"] < 0], key=lambda x: x["weight"])[:3]
                
                selected = pos_contributions + neg_contributions
                
                # Map to spans in the original text (case insensitive)
                for item in selected:
                    pattern = re.compile(re.escape(item["feature"].replace(" ", r"\s+")), re.IGNORECASE)
                    spans = []
                    for match in pattern.finditer(text):
                        spans.append([match.start(), match.end()])
                    item["spans"] = spans
                    
                explanations[str(i)] = {
                    "intercept": intercept,
                    "context": get_category_context(i),
                    "features": selected
                }
                
        # If unflagged, add the closest category
        if status == "no_issue_detected":
            closest_i = np.argmax(probs)
            scores_closest = float(probs[closest_i])
            # We don't add it to categories to flag it, we just keep scores.
            # UI handles closest category via scores dict.
            
        return {
            "id": segment_id,
            "text": text,
            "start": start,
            "end": end,
            "page": page,
            "status": status,
            "reason": None,
            "categories": categories,
            "scores": scores,
            "explanations": explanations
        }

# Global singleton
model_manager = None

def get_model():
    global model_manager
    if model_manager is None:
        model_manager = ModelManager()
    return model_manager
