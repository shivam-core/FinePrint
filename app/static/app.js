// app/static/app.js
document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const views = {
        'nav-analyse': document.getElementById('view-analyse'),
        'nav-compare': document.getElementById('view-compare'),
        'nav-audit': document.getElementById('view-audit')
    };
    
    Object.keys(views).forEach(navId => {
        document.getElementById(navId).addEventListener('click', (e) => {
            e.preventDefault();
            Object.values(views).forEach(v => v.classList.add('hidden'));
            document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
            views[navId].classList.remove('hidden');
            e.target.classList.add('active');
            
            if (navId === 'nav-audit') loadAudit();
        });
    });

    // Input Tabs
    const inputTabs = document.querySelectorAll('.tab');
    const inputContents = {
        'paste': document.getElementById('paste-input'),
        'upload': document.getElementById('upload-input')
    };
    let inputMode = 'paste';
    let uploadedFile = null;
    let extractedData = null;

    inputTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            inputTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            Object.values(inputContents).forEach(c => c.classList.add('hidden'));
            inputMode = tab.dataset.target;
            inputContents[inputMode].classList.remove('hidden');
        });
    });

    // File Dropzone
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const extractionPreview = document.getElementById('extraction-preview');
    const extractedTextInput = document.getElementById('extracted-text-input');
    const previewMeta = document.getElementById('preview-meta');
    
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.style.borderColor = 'var(--platinum)'; });
    dropzone.addEventListener('dragleave', () => dropzone.style.borderColor = 'var(--border)');
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'var(--border)';
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) handleFile(fileInput.files[0]);
    });

    async function handleFile(file) {
        uploadedFile = file;
        const formData = new FormData();
        formData.append('file', file);
        
        showStatus('Extracting text...', true);
        try {
            const res = await fetch('/api/extract', { method: 'POST', body: formData });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Extraction failed');
            
            extractedData = data;
            dropzone.classList.add('hidden');
            extractionPreview.classList.remove('hidden');
            extractedTextInput.value = data.text;
            
            let metaText = `Extracted ${data.characters} characters from ${data.source_name}`;
            if (data.pages) metaText += ` (${data.pages} pages)`;
            previewMeta.textContent = metaText;
            
            showStatus('', false);
            if (data.warnings && data.warnings.length) {
                showStatus('Warnings: ' + data.warnings.join(' | '), false, 'var(--review)');
            }
        } catch (e) {
            showStatus('Error: ' + e.message, false, 'var(--flag)');
            uploadedFile = null;
        }
    }

    // Main Actions
    const btnAnalyse = document.getElementById('btn-analyse');
    const btnClear = document.getElementById('btn-clear');
    const btnLoadExample = document.getElementById('btn-load-example');
    const statusMsg = document.getElementById('status-msg');
    
    let currentAnalysis = null;

    function showStatus(msg, loading=false, color='var(--platinum)') {
        btnAnalyse.disabled = loading;
        if (!msg) {
            statusMsg.classList.add('hidden');
            return;
        }
        statusMsg.textContent = msg;
        statusMsg.style.color = color;
        statusMsg.classList.remove('hidden');
    }

    btnLoadExample.addEventListener('click', () => {
        inputTabs[0].click();
        document.getElementById('text-input').value = 
            "We may change these terms at any time without notice. We may terminate your access at our sole discretion. You can contact customer support through the help page. Our service is provided without warranties to the extent permitted by applicable law.";
    });

    btnClear.addEventListener('click', () => {
        document.getElementById('text-input').value = '';
        extractedTextInput.value = '';
        extractionPreview.classList.add('hidden');
        dropzone.classList.remove('hidden');
        uploadedFile = null;
        extractedData = null;
        fileInput.value = '';
        document.getElementById('results-view').classList.add('hidden');
        document.getElementById('input-card').classList.remove('hidden');
        showStatus('', false);
    });

    btnAnalyse.addEventListener('click', async () => {
        let text = "";
        let sourceName = "Pasted text";
        let sourceType = "text/plain";
        let userEdited = false;

        if (inputMode === 'paste') {
            text = document.getElementById('text-input').value;
            if (!text.trim()) return showStatus('Please enter some text.', false, 'var(--flag)');
        } else {
            if (!extractedData) return showStatus('Please upload a file first.', false, 'var(--flag)');
            text = extractedTextInput.value;
            sourceName = extractedData.source_name;
            sourceType = extractedData.source_type;
            if (text !== extractedData.text) userEdited = true;
        }

        showStatus('Analysing clauses...', true);
        try {
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text, source_name: sourceName, source_type: sourceType, user_edited: userEdited})
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Analysis failed');
            
            currentAnalysis = data;
            renderResults(data);
            showStatus('', false);
        } catch (e) {
            showStatus('Error: ' + e.message, false, 'var(--flag)');
        }
    });

    // Render logic
    const reader = document.getElementById('source-reader');
    const inspectorContent = document.getElementById('inspector-content');
    const inspectorEmpty = document.getElementById('inspector-empty');
    let activeFilter = 'all';

    function renderResults(data) {
        document.getElementById('input-card').classList.add('hidden');
        document.getElementById('results-view').classList.remove('hidden');
        
        document.getElementById('results-meta').textContent = `${data.source_name} • Model ${data.model_version}`;
        
        const sum = data.summary;
        document.getElementById('sum-total').textContent = sum.total;
        document.getElementById('sum-flagged').textContent = sum.potentially_unfair;
        document.getElementById('sum-clear').textContent = sum.no_issue_detected;
        document.getElementById('sum-review').textContent = sum.needs_review;

        renderReader();
        
        inspectorContent.classList.add('hidden');
        inspectorEmpty.classList.remove('hidden');
    }

    function renderReader() {
        if (!currentAnalysis) return;
        
        // Build DOM
        reader.innerHTML = '';
        
        // Simple sequential rendering
        currentAnalysis.segments.forEach((seg, i) => {
            const span = document.createElement('span');
            
            // To handle highlights inside, we replace text.
            // But if filter hides it, we handle visibility.
            span.className = `segment ${seg.status === 'potentially_unfair' ? 'flagged' : (seg.status==='needs_review' ? 'review' : '')}`;
            span.dataset.id = i;
            
            // Highlight text if this is flagged and has features
            let htmlText = seg.text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
            
            span.innerHTML = htmlText;
            
            // Filtering
            if (activeFilter === 'all' || 
                (activeFilter === 'flagged' && seg.status === 'potentially_unfair') ||
                (activeFilter === 'clear' && seg.status === 'no_issue_detected') ||
                (activeFilter === 'review' && seg.status === 'needs_review')) {
                span.style.display = 'inline';
            } else {
                span.style.display = 'none';
            }
            
            span.addEventListener('click', () => selectSegment(i));
            reader.appendChild(span);
        });
    }

    document.querySelectorAll('.filter').forEach(f => {
        f.addEventListener('click', () => {
            document.querySelectorAll('.filter').forEach(btn => btn.classList.remove('active'));
            f.classList.add('active');
            activeFilter = f.dataset.filter;
            renderReader();
        });
    });

    let currentSegmentIndex = null;
    let selectedCatId = null;

    function selectSegment(index) {
        currentSegmentIndex = index;
        document.querySelectorAll('.segment').forEach(s => s.classList.remove('selected'));
        const span = reader.querySelector(`[data-id="${index}"]`);
        if(span) {
            span.classList.add('selected');
            span.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        }
        
        const seg = currentAnalysis.segments[index];
        inspectorEmpty.classList.add('hidden');
        inspectorContent.classList.remove('hidden');
        
        document.getElementById('ins-id').textContent = `Clause ${seg.id}` + (seg.page ? ` • Page ${seg.page}` : '');
        
        const badge = document.getElementById('ins-badge');
        if (seg.status === 'potentially_unfair') {
            badge.textContent = 'Potentially unfair';
            badge.className = 'badge flagged';
        } else if (seg.status === 'no_issue_detected') {
            badge.textContent = 'No issue detected';
            badge.className = 'badge clear';
        } else {
            badge.textContent = 'Needs review';
            badge.className = 'badge review';
        }

        const catContainer = document.getElementById('ins-categories');
        catContainer.innerHTML = '';
        
        if (seg.status === 'potentially_unfair') {
            if (seg.categories.length > 1) {
                const select = document.createElement('select');
                select.className = 'cat-select';
                seg.categories.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = `${c.name} (${c.model_score.toFixed(2)})`;
                    select.appendChild(opt);
                });
                select.addEventListener('change', (e) => {
                    selectedCatId = e.target.value;
                    renderInspectorDetails(seg);
                });
                catContainer.appendChild(select);
                selectedCatId = seg.categories[0].id.toString();
            } else {
                const c = seg.categories[0];
                selectedCatId = c.id.toString();
                catContainer.innerHTML = `<h3 style="margin-bottom:16px;">${c.name}</h3>`;
            }
        } else if (seg.status === 'no_issue_detected') {
            // Find closest
            let maxScore = -1;
            let maxCat = -1;
            for (const [k, v] of Object.entries(seg.scores)) {
                if (v > maxScore) { maxScore = v; maxCat = k; }
            }
            selectedCatId = maxCat;
            catContainer.innerHTML = `<h3 style="margin-bottom:16px; color:var(--muted); font-size:16px;">Closest category: Below threshold</h3>`;
        } else {
            selectedCatId = null;
            catContainer.innerHTML = `<h3 style="margin-bottom:16px;">Reason: ${seg.reason || 'Unknown'}</h3>`;
        }

        renderInspectorDetails(seg);
    }

    function renderInspectorDetails(seg) {
        if (!selectedCatId || !seg.explanations[selectedCatId]) {
            document.getElementById('ins-context').classList.add('hidden');
            document.getElementById('ins-features').classList.add('hidden');
            document.getElementById('ins-score').textContent = '-';
            return;
        }

        const exp = seg.explanations[selectedCatId];
        document.getElementById('ins-context').classList.remove('hidden');
        document.getElementById('ins-context').textContent = exp.context;
        
        const score = seg.scores[selectedCatId];
        let threshold = 0.5;
        if(seg.categories) {
            const cat = seg.categories.find(c => c.id.toString() === selectedCatId);
            if (cat) threshold = cat.threshold;
        }
        
        document.getElementById('ins-score').textContent = `${score.toFixed(3)} (Threshold: ${threshold.toFixed(2)})`;

        const flist = document.getElementById('features-list');
        flist.innerHTML = '';
        if (exp.features && exp.features.length) {
            document.getElementById('ins-features').classList.remove('hidden');
            
            // Normalize weights for bar display
            const maxW = Math.max(...exp.features.map(f => Math.abs(f.weight)));
            
            exp.features.forEach(f => {
                const w = (f.weight / maxW) * 100;
                const sign = f.weight > 0 ? 'pos' : 'neg';
                
                const div = document.createElement('div');
                div.className = 'feature-bar';
                div.innerHTML = `
                    <div class="feature-name" title="${f.feature}">${f.feature}</div>
                    <div class="bar-wrap">
                        <div class="bar-fill ${sign}" style="width: ${Math.abs(w)/2}%"></div>
                    </div>
                    <div class="feature-val ${sign==='pos' ? 'flagged' : 'clear'}" style="color:var(--${sign==='pos'?'flag':'clear'})">${(f.weight>0?'+':'')}${f.weight.toFixed(2)}</div>
                `;
                flist.appendChild(div);
            });
        } else {
            document.getElementById('ins-features').classList.add('hidden');
        }
        
        // Highlight in reader for selected segment
        // We re-render the single span with highlights
        const span = reader.querySelector(`[data-id="${currentSegmentIndex}"]`);
        if (span && exp.features && exp.features.length) {
            let html = seg.text;
            // Get all spans to highlight, flatten and sort
            let ranges = [];
            exp.features.forEach(f => {
                if(f.weight > 0) { // Only highlight positive contributors
                    f.spans.forEach(r => ranges.push(r));
                }
            });
            // Merge overlapping ranges
            ranges.sort((a,b) => a[0] - b[0]);
            let merged = [];
            ranges.forEach(r => {
                if(!merged.length) merged.push([...r]);
                else {
                    let last = merged[merged.length-1];
                    if(r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
                    else merged.push([...r]);
                }
            });
            
            // Apply backward to not mess up indices
            for(let i=merged.length-1; i>=0; i--) {
                const [start, end] = merged[i];
                html = html.substring(0, start) + '<mark class="highlight">' + html.substring(start, end) + '</mark>' + html.substring(end);
            }
            span.innerHTML = html.replace(/\n/g, '<br>');
        }
    }

    // PDF Download
    document.getElementById('btn-download-pdf').addEventListener('click', async () => {
        if (!currentAnalysis) return;
        try {
            const btn = document.getElementById('btn-download-pdf');
            const origText = btn.textContent;
            btn.textContent = 'Generating...';
            btn.disabled = true;

            const res = await fetch('/api/report', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    text: currentAnalysis.text,
                    source_name: currentAnalysis.source_name,
                    source_type: "text/plain"
                })
            });
            
            if (!res.ok) throw new Error('PDF generation failed');
            
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'FinePrint_Analysis_Report.pdf';
            document.body.appendChild(a);
            a.click();
            a.remove();
            
            btn.textContent = origText;
            btn.disabled = false;
        } catch(e) {
            alert('Failed to generate PDF: ' + e.message);
        }
    });

    // Compare Logic
    document.getElementById('btn-comp-demo').addEventListener('click', () => {
        document.getElementById('comp-orig').value = "We may change these terms at any time without notice.";
        document.getElementById('comp-rev').value = "We will notify you at least 30 days before making material changes to these terms.";
    });

    document.getElementById('btn-compare').addEventListener('click', async () => {
        const orig = document.getElementById('comp-orig').value;
        const rev = document.getElementById('comp-rev').value;
        if (!orig || !rev) return alert("Enter both texts");

        document.getElementById('btn-compare').disabled = true;
        try {
            const res = await fetch('/api/compare', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({original: orig, revised: rev})
            });
            const data = await res.json();
            if(!res.ok) throw new Error("Comparison failed");
            
            document.getElementById('comp-results').classList.remove('hidden');
            renderCompareRes('comp-res-orig', 'Original', data.original);
            renderCompareRes('comp-res-rev', 'Revised', data.revised);
            
        } catch (e) {
            alert(e.message);
        }
        document.getElementById('btn-compare').disabled = false;
    });

    function renderCompareRes(id, title, res) {
        const el = document.getElementById(id);
        let catsHtml = res.categories.map(c => `<li>${c.name} (${c.model_score.toFixed(2)})</li>`).join('');
        if(!catsHtml) catsHtml = '<li>None</li>';
        
        el.innerHTML = `
            <h3 style="margin-top:0">${title}</h3>
            <div class="badge ${res.status === 'potentially_unfair' ? 'flagged' : 'clear'}">${res.status.replace(/_/g, ' ')}</div>
            <h4 style="margin-bottom:8px">Categories flagged</h4>
            <ul style="margin-top:0">${catsHtml}</ul>
        `;
    }

    // Audit
    async function loadAudit() {
        try {
            const res = await fetch('/api/audit');
            if(res.ok) {
                const data = await res.json();
                document.getElementById('audit-content').textContent = JSON.stringify(data, null, 2);
            }
        } catch(e) {
            console.error(e);
        }
    }

    document.getElementById('btn-download-model-card').addEventListener('click', () => {
        window.open('/api/model-card', '_blank');
    });
});
