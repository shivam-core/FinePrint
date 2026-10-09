# scripts/train.py
import json
import os
import re
import datetime
from pathlib import Path
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import f1_score
import numpy as np
import joblib

# Ensure reproducible numerical ops where possible
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

def clean_text(text):
    # Normalize whitespace
    return re.sub(r'\s+', ' ', text).strip()

def main():
    print("Loading LexGLUE unfair_tos dataset...")
    dataset = load_dataset("coastalcph/lex_glue", "unfair_tos")
    
    # Process train split
    train_texts = []
    train_labels = []
    seen_train = {}
    
    # The labels field is a list of integers
    for item in dataset["train"]:
        t = clean_text(item["text"])
        if t in seen_train:
            # Union labels for exact duplicates
            seen_train[t] = list(set(seen_train[t]) | set(item["labels"]))
        else:
            seen_train[t] = item["labels"]
    
    for t, labels in seen_train.items():
        train_texts.append(t)
        train_labels.append(labels)
        
    print(f"Train size after deduplication: {len(train_texts)}")

    # Process validation split (remove overlaps with train)
    val_texts = []
    val_labels = []
    seen_val = {}
    for item in dataset["validation"]:
        t = clean_text(item["text"])
        if t in seen_train:
            continue
        if t in seen_val:
            seen_val[t] = list(set(seen_val[t]) | set(item["labels"]))
        else:
            seen_val[t] = item["labels"]
            
    for t, labels in seen_val.items():
        val_texts.append(t)
        val_labels.append(labels)
        
    print(f"Validation size after deduplication and leakage control: {len(val_texts)}")
    
    # Process test split (remove overlaps with train or val)
    test_texts = []
    test_labels = []
    seen_test = {}
    for item in dataset["test"]:
        t = clean_text(item["text"])
        if t in seen_train or t in seen_val:
            continue
        if t in seen_test:
            seen_test[t] = list(set(seen_test[t]) | set(item["labels"]))
        else:
            seen_test[t] = item["labels"]
            
    for t, labels in seen_test.items():
        test_texts.append(t)
        test_labels.append(labels)
        
    print(f"Test size after deduplication and leakage control: {len(test_texts)}")
    
    mlb = MultiLabelBinarizer(classes=list(range(8)))
    y_train = mlb.fit_transform(train_labels)
    y_val = mlb.transform(val_labels)
    
    print("Fitting TfidfVectorizer...")
    vectorizer = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), min_df=2,
        max_df=1.0, max_features=25000, sublinear_tf=True,
        strip_accents=None
    )
    X_train = vectorizer.fit_transform(train_texts)
    X_val = vectorizer.transform(val_texts)
    
    print("Training LogisticRegression (OneVsRest)...")
    clf = OneVsRestClassifier(LogisticRegression(
        C=2.0, class_weight="balanced", solver="liblinear",
        max_iter=1000, random_state=42
    ), n_jobs=1)
    
    clf.fit(X_train, y_train)
    
    # Tune thresholds
    print("Tuning thresholds on validation set...")
    y_val_prob = clf.predict_proba(X_val)
    thresholds = []
    for i in range(8):
        best_t = 0.50
        best_f1 = -1.0
        
        # Check if validation has positives
        if np.sum(y_val[:, i]) == 0:
            thresholds.append(0.50)
            print(f"Class {i} has no positives in val. Using 0.50")
            continue
            
        for t in np.arange(0.20, 0.81, 0.05):
            preds = (y_val_prob[:, i] >= t).astype(int)
            score = f1_score(y_val[:, i], preds, zero_division=0)
            if score > best_f1:
                best_f1 = score
                best_t = t
            elif score == best_f1:
                # Tie break toward 0.50 then larger
                dist_new = abs(t - 0.5)
                dist_old = abs(best_t - 0.5)
                if dist_new < dist_old:
                    best_t = t
                elif dist_new == dist_old and t > best_t:
                    best_t = t
        thresholds.append(round(best_t, 2))
        print(f"Class {i} best threshold: {thresholds[-1]} (F1: {best_f1:.4f})")
        
    print(f"Final thresholds: {thresholds}")
    
    # Median word count for short/long audit
    def word_count(text):
        return len(re.findall(r"\b\w+\b", text))
        
    train_word_counts = [word_count(t) for t in train_texts]
    median_length = float(np.median(train_word_counts))
    print(f"Training median word count: {median_length}")
    
    # Save the model
    os.makedirs("artifacts", exist_ok=True)
    model_data = {
        "vectorizer": vectorizer,
        "classifier": clf,
        "thresholds": thresholds,
        "classes": list(range(8)),
        "median_length": median_length
    }
    
    joblib.dump(model_data, "artifacts/model.joblib", compress=3)
    
    metadata = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_version": "v1.0",
        "feature_count": len(vectorizer.get_feature_names_out()),
        "thresholds": thresholds,
        "median_length": median_length,
        "train_size": len(train_texts),
        "val_size": len(val_texts),
        "test_size": len(test_texts)
    }
    
    with open("artifacts/metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    with open("docs/data_provenance.json", "w", encoding="utf-8") as f:
        json.dump({
            "dataset": "LexGLUE unfair_tos",
            "source": "https://huggingface.co/datasets/coastalcph/lex_glue",
            "train_retained": len(train_texts),
            "val_retained": len(val_texts),
            "test_retained": len(test_texts),
            "deduplication": "Union labels for exact duplicates, removed overlaps in val/test."
        }, f, indent=2)
        
    # We also need to save the test set for evaluate.py
    test_data = {
        "texts": test_texts,
        "labels": test_labels
    }
    joblib.dump(test_data, "artifacts/test_data.joblib", compress=3)
        
    print("Training complete. Artifacts saved.")

if __name__ == "__main__":
    main()
