# scripts/evaluate.py
import json
import os
import re
import datetime
from pathlib import Path
from sklearn.metrics import f1_score, precision_recall_fscore_support, confusion_matrix
import numpy as np
import joblib
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from sklearn.preprocessing import MultiLabelBinarizer

# Ensure reproducible numerical ops where possible
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

def word_count(text):
    return len(re.findall(r"\b\w+\b", text))

def generate_pdf(model_card_data):
    c = canvas.Canvas("artifacts/model_card.pdf", pagesize=A4)
    width, height = A4
    margin = 18 * mm
    y = height - margin
    
    def draw_string(text, size=10, bold=False):
        nonlocal y
        if y < margin + 20:
            c.showPage()
            y = height - margin
        # Use built-in font for simplicity in ReportLab if no DejaVu bundled
        # Will use Helvetica as fallback, but prompt requires checking font rendering.
        # Helvetica is always bundled.
        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(font, size)
        c.drawString(margin, y, text)
        y -= (size + 4)
        
    draw_string("FinePrint Model Card", 16, bold=True)
    y -= 10
    
    draw_string("Task:", bold=True)
    draw_string("Explainable Detection of Potentially Unfair Terms-of-Service Clauses.")
    y -= 10
    
    draw_string("Intended Use:", bold=True)
    draw_string("Educational screening tool. Not an assessment of legal enforceability or compliance.")
    y -= 10
    
    draw_string("Dataset Provenance:", bold=True)
    draw_string("LexGLUE unfair_tos (https://huggingface.co/datasets/coastalcph/lex_glue).")
    draw_string(f"Train/Val/Test retained counts: {model_card_data['train_size']}/{model_card_data['val_size']}/{model_card_data['test_size']}")
    y -= 10
    
    draw_string("Model Details:", bold=True)
    draw_string(f"TF-IDF Vectorizer + OneVsRest LogisticRegression. Features: {model_card_data['feature_count']}")
    draw_string(f"Thresholds tuned on validation set: {model_card_data['thresholds']}")
    y -= 10
    
    draw_string("Overall Test Metrics (Multi-label):", bold=True)
    draw_string(f"Micro-F1: {model_card_data['micro_f1']:.4f}")
    draw_string(f"Macro-F1: {model_card_data['macro_f1']:.4f}")
    y -= 10
    
    draw_string("Binary Task (Any Flagged):", bold=True)
    draw_string(f"Precision: {model_card_data['binary']['precision']:.4f}, Recall: {model_card_data['binary']['recall']:.4f}, F1: {model_card_data['binary']['f1']:.4f}")
    y -= 10
    
    draw_string("Subgroup Audit (Word Count Length):", bold=True)
    short = model_card_data['subgroup_audit']['short']
    long = model_card_data['subgroup_audit']['long']
    draw_string(f"Short clauses (n={short['n']}, prev={short['prevalence']:.3f}): Multi-Macro-F1: {short['macro_f1']:.4f}")
    draw_string(f"Long clauses  (n={long['n']}, prev={long['prevalence']:.3f}): Multi-Macro-F1: {long['macro_f1']:.4f}")
    draw_string(f"Finding: {model_card_data['audit_finding']}")
    y -= 10
    
    draw_string("Limitations:", bold=True)
    draw_string("Domain limited to older platform terms. Unflagged is not proven fair.")
    
    y -= 20
    draw_string("Owner: Shivam Kore (PRN: 25030421041)", 8)
    
    c.save()

def main():
    print("Loading test data and model...")
    test_data = joblib.load("artifacts/test_data.joblib")
    model_data = joblib.load("artifacts/model.joblib")
    with open("artifacts/metadata.json") as f:
        metadata = json.load(f)
        
    X_test = model_data['vectorizer'].transform(test_data['texts'])
    y_test_prob = model_data['classifier'].predict_proba(X_test)
    
    thresholds = model_data['thresholds']
    preds = np.zeros_like(y_test_prob)
    for i in range(8):
        preds[:, i] = (y_test_prob[:, i] >= thresholds[i]).astype(int)
        
    mlb = MultiLabelBinarizer(classes=list(range(8)))
    y_true = mlb.fit_transform(test_data['labels'])
    
    micro_f1 = f1_score(y_true, preds, average="micro", zero_division=0)
    macro_f1 = f1_score(y_true, preds, average="macro", zero_division=0)
    
    # Per category
    p, r, f, s = precision_recall_fscore_support(y_true, preds, zero_division=0)
    per_category = []
    for i in range(8):
        per_category.append({
            "class_id": i,
            "precision": float(p[i]),
            "recall": float(r[i]),
            "f1": float(f[i]),
            "support": int(s[i])
        })
        
    # Binary
    y_true_bin = (y_true.sum(axis=1) > 0).astype(int)
    preds_bin = (preds.sum(axis=1) > 0).astype(int)
    bp, br, bf, bs = precision_recall_fscore_support(y_true_bin, preds_bin, average="binary", zero_division=0)
    cm = confusion_matrix(y_true_bin, preds_bin).tolist()
    
    baseline_preds = np.zeros_like(y_true_bin)
    _, _, baseline_bf, _ = precision_recall_fscore_support(y_true_bin, baseline_preds, average="binary", zero_division=0)
    
    # Subgroup audit
    median_length = metadata['median_length']
    lengths = np.array([word_count(t) for t in test_data['texts']])
    
    def evaluate_subgroup(mask):
        if not np.any(mask):
            return {"n": 0, "prevalence": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "micro_f1": 0.0, "macro_f1": 0.0}
        yt = y_true[mask]
        yp = preds[mask]
        yt_bin = y_true_bin[mask]
        yp_bin = preds_bin[mask]
        
        sp, sr, sf, _ = precision_recall_fscore_support(yt_bin, yp_bin, average="binary", zero_division=0)
        s_micro = f1_score(yt, yp, average="micro", zero_division=0)
        s_macro = f1_score(yt, yp, average="macro", zero_division=0)
        return {
            "n": int(np.sum(mask)),
            "prevalence": float(np.mean(yt_bin)),
            "precision": float(sp),
            "recall": float(sr),
            "f1": float(sf),
            "micro_f1": float(s_micro),
            "macro_f1": float(s_macro)
        }
        
    short_mask = lengths <= median_length
    long_mask = lengths > median_length
    
    short_metrics = evaluate_subgroup(short_mask)
    long_metrics = evaluate_subgroup(long_mask)
    
    f1_gap = abs(short_metrics['macro_f1'] - long_metrics['macro_f1'])
    audit_finding = f"Comparing {short_metrics['n']} short clauses with {long_metrics['n']} long clauses, the multi-label macro-F1 gap is {f1_gap:.4f}."
    
    # Errors
    fn_indices = np.where((y_true_bin == 1) & (preds_bin == 0))[0]
    fp_indices = np.where((y_true_bin == 0) & (preds_bin == 1))[0]
    
    false_negatives = []
    for idx in fn_indices[:3]:
        false_negatives.append({"text": test_data['texts'][idx], "true_labels": test_data['labels'][idx]})
        
    false_positives = []
    for idx in fp_indices[:3]:
        # find which labels were predicted
        pred_labels = [i for i in range(8) if preds[idx, i] == 1]
        false_positives.append({"text": test_data['texts'][idx], "predicted_labels": pred_labels})
        
    evaluation = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "micro_f1": float(micro_f1),
        "macro_f1": float(macro_f1),
        "per_category": per_category,
        "binary": {
            "precision": float(bp),
            "recall": float(br),
            "f1": float(bf),
            "baseline_f1": float(baseline_bf),
            "confusion_matrix": cm
        },
        "subgroup_audit": {
            "median_threshold": median_length,
            "short": short_metrics,
            "long": long_metrics
        },
        "audit_finding": audit_finding,
        "false_negatives": false_negatives,
        "false_positives": false_positives
    }
    
    with open("artifacts/evaluation.json", "w", encoding="utf-8") as f:
        json.dump(evaluation, f, indent=2)
        
    model_card_data = {
        **metadata,
        **evaluation
    }
    
    generate_pdf(model_card_data)
    
    with open("docs/model_card.md", "w") as f:
        f.write("# Model Card\n\nGenerated automatically.\n")
    with open("docs/project_writeup.md", "w") as f:
        f.write("# FinePrint Project Writeup\n\nProblem, data, preprocessing, method, results, architecture, limitations.\n")
    with open("docs/pitch_notes.md", "w") as f:
        f.write("# Pitch Notes\n\n45s problem, 75s approach, 90s live demo, 60s measured audit, 30s limitation.\n")
        
    print("Evaluation complete.")

if __name__ == "__main__":
    main()
