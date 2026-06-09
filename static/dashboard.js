// Dashboard JavaScript
console.log('Dashboard.js loaded');

const ICON_EDIT = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4z"/></svg>`;
const ICON_DELETE = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`;
const ICON_UPLOAD = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>`;

class Dashboard {
    constructor() {
        console.log('Dashboard constructor called');
        this.currentTab = 'collections';
        this.currentCollection = '';
        this.collections = [];
        this.documents = [];
        this.queryRuns = [];
        this.init();
    }

    init() {
        console.log('Dashboard init() called');
        try {
            this.setupEventListeners();
            this.loadCollections();
            this.loadCollectionsGrid(); // Load collections grid on startup
            this.loadData();
            console.log('Dashboard init() completed successfully');
        } catch (error) {
            console.error('Error in Dashboard init():', error);
        }
    }

    setupEventListeners() {
        console.log('Setting up event listeners...');
        // Tab navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Refresh button
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadData();
            });
        }

        // Collection filter
        const collectionFilter = document.getElementById('collectionFilter');
        if (collectionFilter) {
            collectionFilter.addEventListener('change', (e) => {
                this.currentCollection = e.target.value;
                this.loadData();
            });
        }

        // Document filters
        const statusFilter = document.getElementById('statusFilter');
        if (statusFilter) {
            statusFilter.addEventListener('change', () => {
                this.filterDocuments();
            });
        }
        const typeFilter = document.getElementById('typeFilter');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => {
                this.filterDocuments();
            });
        }
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                this.filterDocuments();
            });
        }

        // Create collection button
        const createCollectionBtn = document.getElementById('createCollectionBtn');
        if (createCollectionBtn) {
            createCollectionBtn.addEventListener('click', () => {
                this.showCreateCollectionModal();
            });
        }

        // Create document button
        const createDocBtn = document.getElementById('createDocBtn');
        if (createDocBtn) {
            createDocBtn.addEventListener('click', () => {
                this.showCreateDocModal();
            });
        }

        // Modal close buttons
        document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.modal').classList.remove('active');
            });
        });

        // Create document form
        const createDocForm = document.getElementById('createDocForm');
        if (createDocForm) {
            createDocForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createDocument(e.target);
            });
        }

        // Evaluation form
        const evaluationForm = document.getElementById('evaluationForm');
        if (evaluationForm) {
            evaluationForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitEvaluation(e.target);
            });
        }

        // Star rating
        document.querySelectorAll('.star').forEach(star => {
            star.addEventListener('click', (e) => {
                const value = e.target.dataset.value;
                this.setStarRating(value);
            });
        });

        // Range inputs
        document.querySelectorAll('input[type="range"]').forEach(input => {
            input.addEventListener('input', (e) => {
                e.target.nextElementSibling.textContent = e.target.value;
            });
        });

        // Create collection form
        const createCollectionForm = document.getElementById('createCollectionForm');
        if (createCollectionForm) {
            createCollectionForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createCollection(e.target);
            });
        }

        // Upload PDF form
        const uploadPdfForm = document.getElementById('uploadPdfForm');
        if (uploadPdfForm) {
            uploadPdfForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.uploadPdf(e.target);
            });
        }

        // Collection tabs
        document.querySelectorAll('.collection-tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.target.dataset.tab;
                document.querySelectorAll('.collection-tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.collection-tab-pane').forEach(p => p.classList.remove('active'));
                e.target.classList.add('active');
                document.getElementById(`collection${tab.charAt(0).toUpperCase() + tab.slice(1)}Tab`).classList.add('active');
                
                // Load settings when settings tab is clicked
                if (tab === 'settings' && this.currentCollection) {
                    this.loadCollectionSettings(this.currentCollection);
                }
            });
        });

        // Collection settings form
        const settingsForm = document.getElementById('collectionSettingsForm');
        if (settingsForm) {
            settingsForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveCollectionSettings(e.target);
            });
        }

        // Add document button in collection modal - shows 3-tab interface
        const addDocBtn = document.getElementById('addDocumentBtn');
        if (addDocBtn) {
            addDocBtn.addEventListener('click', () => {
                const docInterface = document.getElementById('dashboardAddDocumentInterface');
                if (docInterface) {
                    docInterface.style.display = 'block';
                    this.switchDashboardTab('uploadPdf');
                }
            });
        }

        // Dashboard tab switching
        document.getElementById('tabDashboardUploadPdf')?.addEventListener('click', () => this.switchDashboardTab('uploadPdf'));
        document.getElementById('tabDashboardAddManual')?.addEventListener('click', () => this.switchDashboardTab('addManual'));
        document.getElementById('tabDashboardImportCsv')?.addEventListener('click', () => this.switchDashboardTab('importCsv'));
        document.getElementById('tabDashboardImportRis')?.addEventListener('click', () => this.switchDashboardTab('importRis'));

        // Dashboard form submissions
        document.getElementById('dashboardUploadPdfForm')?.addEventListener('submit', (e) => this.handleDashboardUploadPdf(e));
        document.getElementById('dashboardAddManualForm')?.addEventListener('submit', (e) => this.handleDashboardAddManual(e));
        document.getElementById('dashboardImportCsvForm')?.addEventListener('submit', (e) => this.handleDashboardImportCsv(e));
        document.getElementById('dashboardImportRisForm')?.addEventListener('submit', (e) => this.handleDashboardImportRis(e));

        // PDF Tools
        document.getElementById('scanLocalPdfsBtn')?.addEventListener('click', () => this.handleScanLocalPdfs());
        document.getElementById('fetchOpenAccessBtn')?.addEventListener('click', () => this.handleFetchOpenAccess());
        document.getElementById('processQueuedBtn')?.addEventListener('click', () => this.handleProcessQueued());
    }

    switchDashboardTab(tabName) {
        // Update tab buttons
        const tabs = document.querySelectorAll('#dashboardAddDocumentInterface .docs-tab');
        tabs.forEach(tab => {
            if (tab.id === `tabDashboard${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`) {
                tab.style.borderBottom = '3px solid #10b981';
                tab.style.fontWeight = '600';
            } else {
                tab.style.borderBottom = '3px solid transparent';
                tab.style.fontWeight = 'normal';
            }
        });

        // Update tab content
        document.getElementById('dashboardUploadPdfTab').style.display = tabName === 'uploadPdf' ? 'block' : 'none';
        document.getElementById('dashboardAddManualTab').style.display = tabName === 'addManual' ? 'block' : 'none';
        document.getElementById('dashboardImportCsvTab').style.display = tabName === 'importCsv' ? 'block' : 'none';
        document.getElementById('dashboardImportRisTab').style.display = tabName === 'importRis' ? 'block' : 'none';
    }

    async handleDashboardUploadPdf(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('dashboardUploadPdfFile');
        const file = fileInput.files[0];
        const collection = this.currentCollection;
        
        if (!file) {
            this.showStatus('dashboardUploadPdfStatus', 'Please select a PDF file', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('collection', collection);

        this.showProgress('dashboardUploadPdf', 'Uploading...', 0);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.status === 'success') {
                this.showProgress('dashboardUploadPdf', 'Upload complete!', 100);
                this.showStatus('dashboardUploadPdfStatus', 'Document uploaded successfully!', 'success');
                
                setTimeout(() => {
                    document.getElementById('dashboardAddDocumentInterface').style.display = 'none';
                    this.loadCollectionDocuments(collection);
                }, 1500);
            } else {
                this.showStatus('dashboardUploadPdfStatus', result.message || 'Upload failed', 'error');
                document.getElementById('dashboardUploadPdfProgressWrap').style.display = 'none';
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showStatus('dashboardUploadPdfStatus', 'Upload failed: ' + error.message, 'error');
            document.getElementById('dashboardUploadPdfProgressWrap').style.display = 'none';
        }
    }

    async handleDashboardAddManual(e) {
        e.preventDefault();

        const title = document.getElementById('dashboardManualTitle').value.trim();
        const collection = this.currentCollection;
        
        if (!title) {
            this.showStatus('dashboardAddManualStatus', 'Title is required', 'error');
            return;
        }

        const tags = document.getElementById('dashboardManualTags').value.trim();
        const payload = {
            collection: collection,
            title: title,
            author: document.getElementById('dashboardManualAuthor').value.trim() || null,
            year: document.getElementById('dashboardManualYear').value ? parseInt(document.getElementById('dashboardManualYear').value) : null,
            document_type: document.getElementById('dashboardManualDocType').value || null,
            doi: document.getElementById('dashboardManualDoi').value.trim() || null,
            abstract: document.getElementById('dashboardManualAbstract').value.trim() || null,
            notes: document.getElementById('dashboardManualNotes').value.trim() || null,
            tags: tags ? tags.split(',').map(t => t.trim()).filter(t => t) : null,
            apa7_reference: document.getElementById('dashboardManualApa7').value.trim() || null
        };

        this.showStatus('dashboardAddManualStatus', 'Creating document...', 'info');

        try {
            const response = await fetch('/api/documents/add-manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (result.status === 'success') {
                this.showStatus('dashboardAddManualStatus', 'Document created successfully!', 'success');
                
                setTimeout(() => {
                    document.getElementById('dashboardAddDocumentInterface').style.display = 'none';
                    this.loadCollectionDocuments(collection);
                }, 1500);
            } else {
                this.showStatus('dashboardAddManualStatus', result.message || 'Failed to create document', 'error');
            }
        } catch (error) {
            console.error('Create document error:', error);
            this.showStatus('dashboardAddManualStatus', 'Failed to create document: ' + error.message, 'error');
        }
    }

    async handleDashboardImportCsv(e) {
        e.preventDefault();

        const fileInput = document.getElementById('dashboardImportCsvFile');
        const file = fileInput.files[0];
        const collection = this.currentCollection;

        if (!file) {
            this.showStatus('dashboardImportCsvStatus', 'Please select a CSV file', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('collection', collection);

        this.showStatus('dashboardImportCsvStatus', 'Importing documents...', 'info');

        try {
            const response = await fetch('/api/documents/bulk-import', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.status === 'success' || result.imported_count > 0) {
                this.showStatus('dashboardImportCsvStatus', '', '');
                this.showDashboardImportResults(result);
                
                setTimeout(() => {
                    document.getElementById('dashboardAddDocumentInterface').style.display = 'none';
                    this.loadCollectionDocuments(collection);
                }, 3000);
            } else {
                this.showStatus('dashboardImportCsvStatus', result.message || 'Import failed', 'error');
            }
        } catch (error) {
            console.error('Import error:', error);
            this.showStatus('dashboardImportCsvStatus', 'Import failed: ' + error.message, 'error');
        }
    }

    showProgress(prefix, text, percent) {
        const progressWrap = document.getElementById(`${prefix}ProgressWrap`);
        const progressText = document.getElementById(`${prefix}ProgressText`);
        const progressPct = document.getElementById(`${prefix}ProgressPct`);
        const progressBar = document.getElementById(`${prefix}ProgressBar`);

        if (progressWrap) progressWrap.style.display = 'block';
        if (progressText) progressText.textContent = text;
        if (progressPct) progressPct.textContent = `${percent}%`;
        if (progressBar) progressBar.style.width = `${percent}%`;
    }

    showStatus(elementId, message, type) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.textContent = message;
        element.style.padding = message ? '8px 12px' : '0';
        element.style.borderRadius = '4px';
        element.style.marginBottom = message ? '12px' : '0';
        
        if (type === 'error') {
            element.style.background = '#fee2e2';
            element.style.color = '#991b1b';
        } else if (type === 'success') {
            element.style.background = '#d1fae5';
            element.style.color = '#065f46';
        } else if (type === 'info') {
            element.style.background = '#dbeafe';
            element.style.color = '#1e40af';
        } else {
            element.style.background = 'transparent';
            element.style.color = 'inherit';
        }
    }

    async handleScanLocalPdfs() {
        const collection = this.currentCollection;
        if (!collection) { this.showPdfToolsStatus('No collection selected', 'error'); return; }
        this.showPdfToolsStatus('Scanning local folder…', 'info');
        const btn = document.getElementById('scanLocalPdfsBtn');
        if (btn) btn.disabled = true;
        try {
            const fd = new FormData();
            fd.append('collection', collection);
            const resp = await fetch('/api/documents/find-pdfs/local', { method: 'POST', body: fd });
            const result = await resp.json();
            if (!resp.ok) {
                this.showPdfToolsStatus(result.detail || 'Scan failed', 'error');
            } else if (result.status === 'nothing_to_match') {
                this.showPdfToolsStatus('All records already have PDFs attached.', 'success');
            } else {
                this.showPdfToolsStatus(`Found ${result.unattached_count} unattached records — ingesting matched PDFs…`, 'info');
                this._startProgressPolling(collection);
            }
        } catch (err) {
            this.showPdfToolsStatus('Scan failed: ' + err.message, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async handleFetchOpenAccess() {
        const collection = this.currentCollection;
        if (!collection) { this.showPdfToolsStatus('No collection selected', 'error'); return; }
        this.showPdfToolsStatus('Queuing Unpaywall lookups…', 'info');
        const btn = document.getElementById('fetchOpenAccessBtn');
        if (btn) btn.disabled = true;
        try {
            const fd = new FormData();
            fd.append('collection', collection);
            const resp = await fetch('/api/documents/find-pdfs/open-access', { method: 'POST', body: fd });
            const result = await resp.json();
            if (!resp.ok) {
                this.showPdfToolsStatus(result.detail || 'Fetch failed', 'error');
            } else if (result.status === 'nothing_to_fetch') {
                this.showPdfToolsStatus('No unattached records with DOIs found.', 'success');
            } else {
                this.showPdfToolsStatus(`Fetching open-access PDFs for ${result.queued} records via Unpaywall…`, 'info');
                this._startProgressPolling(collection);
            }
        } catch (err) {
            this.showPdfToolsStatus('Fetch failed: ' + err.message, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async handleProcessQueued() {
        const collection = this.currentCollection;
        if (!collection) { this.showPdfToolsStatus('No collection selected', 'error'); return; }
        this.showPdfToolsStatus('Starting ingestion for queued documents…', 'info');
        const btn = document.getElementById('processQueuedBtn');
        if (btn) btn.disabled = true;
        try {
            const resp = await fetch(`/api/documents/process-queued/${encodeURIComponent(collection)}`, { method: 'POST' });
            const result = await resp.json();
            if (!resp.ok) {
                this.showPdfToolsStatus(result.detail || 'Failed to start processing', 'error');
            } else if (result.status === 'nothing_to_process') {
                this.showPdfToolsStatus('No queued documents with attached PDFs found.', 'success');
            } else {
                this.showPdfToolsStatus(`Ingesting ${result.queued} queued document(s)…`, 'info');
                this._startProgressPolling(collection);
            }
        } catch (err) {
            this.showPdfToolsStatus('Error: ' + err.message, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    _startProgressPolling(collection) {
        // Clear any existing poll
        if (this._progressInterval) clearInterval(this._progressInterval);
        const progressDiv = document.getElementById('pdfToolsProgress');
        const logDiv = document.getElementById('progressLog');
        const doneMsg = document.getElementById('progressDoneMsg');
        if (progressDiv) progressDiv.style.display = 'block';
        if (doneMsg) doneMsg.style.display = 'none';
        if (logDiv) logDiv.innerHTML = '';
        let prevCounts = {};
        let stableRounds = 0;

        const poll = async () => {
            try {
                const resp = await fetch(`/api/documents/ingest-status/${encodeURIComponent(collection)}`);
                if (!resp.ok) return;
                const data = await resp.json();
                const c = data.counts || {};
                const complete = c.complete || 0;
                const processing = c.processing || 0;
                const queued = c.queued || 0;
                const failed = c.failed || 0;

                document.getElementById('progressComplete').textContent = complete;
                document.getElementById('progressProcessing').textContent = processing;
                document.getElementById('progressQueued').textContent = queued;
                document.getElementById('progressFailed').textContent = failed;

                // Log lines for changes
                if (logDiv) {
                    const changes = [];
                    if ((c.complete || 0) > (prevCounts.complete || 0))
                        changes.push(`✓ ${(c.complete||0) - (prevCounts.complete||0)} document(s) ingested successfully`);
                    if ((c.failed || 0) > (prevCounts.failed || 0))
                        changes.push(`✗ ${(c.failed||0) - (prevCounts.failed||0)} document(s) failed`);
                    if (changes.length) {
                        const ts = new Date().toLocaleTimeString();
                        changes.forEach(msg => {
                            const line = document.createElement('div');
                            line.textContent = `[${ts}] ${msg}`;
                            logDiv.appendChild(line);
                        });
                        logDiv.scrollTop = logDiv.scrollHeight;
                    }
                }
                prevCounts = { ...c };

                // Stop when nothing is actively being processed
                if (queued === 0 && processing === 0) {
                    stableRounds++;
                    if (stableRounds >= 2) {
                        clearInterval(this._progressInterval);
                        this._progressInterval = null;
                        if (doneMsg) doneMsg.style.display = 'block';
                        setTimeout(() => {
                            if (this.loadCollectionDocuments) this.loadCollectionDocuments(collection);
                        }, 1500);
                    }
                } else {
                    stableRounds = 0;
                }
            } catch (e) { /* ignore transient errors */ }
        };

        poll(); // immediate first check
        this._progressInterval = setInterval(poll, 3000);
    }

    showPdfToolsStatus(message, type) {
        this.showStatus('pdfToolsStatus', message, type);
        const body = document.getElementById('pdfToolsBody');
        if (body) body.style.display = 'block';
    }

    async handleDashboardImportRis(e) {
        e.preventDefault();

        const fileInput = document.getElementById('dashboardImportRisFile');
        const file = fileInput.files[0];
        const collection = this.currentCollection;

        if (!file) {
            this.showStatus('dashboardImportRisStatus', 'Please select a RIS file', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('collection', collection);

        this.showStatus('dashboardImportRisStatus', 'Inserting records...', 'info');

        try {
            const response = await fetch('/api/documents/import-ris', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.status === 'success' || result.imported_count > 0) {
                this.showStatus('dashboardImportRisStatus', '', '');
                this.showDashboardRisImportResults(result);

                setTimeout(() => {
                    document.getElementById('dashboardAddDocumentInterface').style.display = 'none';
                    this.loadCollectionDocuments(collection);
                }, 4000);
            } else {
                const errMsg = result.detail || result.message || result.errors?.[0]?.error || 'Import failed';
                this.showStatus('dashboardImportRisStatus', errMsg, 'error');
            }
        } catch (error) {
            console.error('RIS import error:', error);
            this.showStatus('dashboardImportRisStatus', 'Import failed: ' + error.message, 'error');
        }
    }

    showDashboardRisImportResults(result) {
        const resultsDiv = document.getElementById('dashboardImportRisResults');
        const successCount = document.getElementById('dashboardRisSuccessCount');
        const enrichedCount = document.getElementById('dashboardRisEnrichedCount');
        const notFoundCount = document.getElementById('dashboardRisNotFoundCount');
        const errorCount = document.getElementById('dashboardRisErrorCount');
        const errorList = document.getElementById('dashboardRisErrorList');

        if (successCount) successCount.textContent = result.imported_count || 0;

        const queued = result.crossref_queued || 0;
        if (enrichedCount) enrichedCount.textContent = queued > 0 ? `${queued} queued…` : '0';
        if (notFoundCount) notFoundCount.textContent = '—';
        if (errorCount) errorCount.textContent = result.error_count || 0;

        if (errorList) {
            const msgs = [];
            if (queued > 0) {
                msgs.push(`<div style="padding: 6px 0; color: #1e40af;">CrossRef enrichment is running in the background for ${queued} records. Check the server log or refresh the document list to see results.</div>`);
            }
            if (result.errors && result.errors.length > 0) {
                result.errors.forEach(err => {
                    msgs.push(`<div style="padding: 6px 0; color: #991b1b; border-bottom: 1px solid #fee2e2;">Row ${err.row}: ${err.error}</div>`);
                });
            }
            errorList.innerHTML = msgs.join('');
        }

        if (resultsDiv) resultsDiv.style.display = 'block';
    }

    showDashboardImportResults(result) {
        const resultsDiv = document.getElementById('dashboardImportCsvResults');
        const successCount = document.getElementById('dashboardImportSuccessCount');
        const errorCount = document.getElementById('dashboardImportErrorCount');
        const errorList = document.getElementById('dashboardImportErrorList');

        if (successCount) successCount.textContent = result.imported_count || 0;
        if (errorCount) errorCount.textContent = result.error_count || 0;

        if (errorList) {
            if (result.errors && result.errors.length > 0) {
                errorList.innerHTML = result.errors.map(err => 
                    `<div style="padding: 6px 0; color: #991b1b; border-bottom: 1px solid #fee2e2;">Row ${err.row}: ${err.error}</div>`
                ).join('');
            } else {
                errorList.innerHTML = '';
            }
        }

        if (resultsDiv) resultsDiv.style.display = 'block';
    }

    switchTab(tabName) {
        this.currentTab = tabName;
        
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update tab panes
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `${tabName}-tab`);
        });

        // Load tab-specific data
        if (tabName === 'collections') {
            this.loadCollectionsGrid();
        } else if (tabName === 'documents') {
            this.loadDocuments();
        } else if (tabName === 'ingestion') {
            this.loadIngestionData();
        } else if (tabName === 'analytics') {
            this.loadAnalytics();
        } else if (tabName === 'evaluation') {
            this.loadEvaluations();
        }
    }

    async loadCollections() {
        try {
            const response = await fetch('/collections');
            const data = await response.json();
            
            const select = document.getElementById('collectionFilter');
            select.innerHTML = '<option value="">All Collections</option>';
            
            if (data.collections) {
                data.collections.forEach(coll => {
                    const option = document.createElement('option');
                    option.value = coll.name;
                    option.textContent = coll.name;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading collections:', error);
        }
    }

    async loadData() {
        if (this.currentTab === 'documents') {
            await this.loadDocuments();
        } else if (this.currentTab === 'ingestion') {
            await this.loadIngestionData();
        } else if (this.currentTab === 'analytics') {
            await this.loadAnalytics();
        } else if (this.currentTab === 'evaluation') {
            await this.loadEvaluations();
        }
    }

    async loadDocuments() {
        try {
            const params = new URLSearchParams();
            if (this.currentCollection) {
                params.append('collection', this.currentCollection);
            }
            params.append('limit', '100');

            const response = await fetch(`/api/documents?${params}`);
            const data = await response.json();

            if (data.status === 'success') {
                this.documents = data.documents || [];
                this.renderDocuments(this.documents);
            } else {
                this.showError('Failed to load documents');
            }
        } catch (error) {
            console.error('Error loading documents:', error);
            this.showError('Error loading documents');
        }
    }

    renderDocuments(documents) {
        const tbody = document.getElementById('documentsTableBody');
        
        if (documents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No documents found</td></tr>';
            return;
        }

        tbody.innerHTML = documents.map(doc => {
            const title = this.escapeHtml(doc.title || 'Untitled');
            const needsUpload = !doc.pdf_attached || doc.ingestion_status === 'failed' || doc.ingestion_status === 'not_uploaded';
            const uploadBtn = needsUpload
                ? `<button class="btn-icon btn-icon--success" title="Upload PDF" onclick="dashboard.showUploadPdfForDocument(${doc.id}, '${title}')">${ICON_UPLOAD}</button>`
                : '';
            return `
                <tr>
                    <td class="cell-truncate"><div class="cell-inner cell-inner--bold" title="${title}">${title}</div></td>
                    <td class="cell-truncate"><div class="cell-inner">${this.escapeHtml(doc.document_type || '-')}</div></td>
                    <td class="cell-truncate"><div class="cell-inner">${this.escapeHtml(doc.author || '-')}</div></td>
                    <td>${doc.year || '-'}</td>
                    <td>${doc.pdf_attached ? '✓' : '–'}</td>
                    <td><span class="status-badge status-${doc.ingestion_status}">${doc.ingestion_status || 'unknown'}</span></td>
                    <td>${doc.times_retrieved || 0}</td>
                    <td>${doc.times_cited || 0}</td>
                    <td>${doc.avg_overall_score ? doc.avg_overall_score.toFixed(1) : '-'}</td>
                    <td class="cell-actions">
                        ${uploadBtn}
                        <button class="btn-icon btn-icon--primary" title="Edit" onclick="dashboard.editDocument(${doc.id})">${ICON_EDIT}</button>
                        <button class="btn-icon btn-icon--danger" title="Delete" onclick="dashboard.deleteDocument(${doc.id}, '${title}')">${ICON_DELETE}</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    filterDocuments() {
        const status = document.getElementById('statusFilter').value;
        const type = document.getElementById('typeFilter').value;
        const search = document.getElementById('searchInput').value.toLowerCase();

        const filtered = this.documents.filter(doc => {
            if (status && doc.ingestion_status !== status) return false;
            if (type && doc.document_type !== type) return false;
            if (search) {
                const searchText = `${doc.title} ${doc.author} ${doc.notes}`.toLowerCase();
                if (!searchText.includes(search)) return false;
            }
            return true;
        });

        this.renderDocuments(filtered);
    }

    async loadIngestionData() {
        try {
            const statuses = ['queued', 'processing', 'complete', 'failed'];
            
            for (const status of statuses) {
                const params = new URLSearchParams({ status, limit: '20' });
                if (this.currentCollection) {
                    params.append('collection', this.currentCollection);
                }

                const response = await fetch(`/api/ingestion/jobs?${params}`);
                const data = await response.json();

                if (data.status === 'success') {
                    this.renderIngestionJobs(status, data.jobs || []);
                }
            }
        } catch (error) {
            console.error('Error loading ingestion data:', error);
        }
    }

    renderIngestionJobs(status, jobs) {
        const container = document.getElementById(`${status}Jobs`);
        const countEl = document.getElementById(`${status}Count`);
        
        countEl.textContent = jobs.length;

        if (jobs.length === 0) {
            container.innerHTML = '<p class="empty-state">No jobs</p>';
            return;
        }

        container.innerHTML = jobs.map(job => `
            <div class="job-item">
                <h4>${this.escapeHtml(job.doc_id || 'Unknown')}</h4>
                <p>Collection: ${this.escapeHtml(job.collection)}</p>
                <p>Started: ${new Date(job.started_at).toLocaleString()}</p>
                ${job.chunks_created ? `<p>Chunks: ${job.chunks_created}</p>` : ''}
                ${job.error_message ? `<p class="job-error">Error: ${this.escapeHtml(job.error_message)}</p>` : ''}
            </div>
        `).join('');
    }

    async loadAnalytics() {
        try {
            // Load document analytics
            const docParams = new URLSearchParams();
            if (this.currentCollection) {
                docParams.append('collection', this.currentCollection);
            }

            const docResponse = await fetch(`/api/analytics/documents?${docParams}`);
            const docData = await docResponse.json();

            if (docData.status === 'success') {
                this.renderDocumentAnalytics(docData.analytics);
            }

            // Load retrieval mode analytics
            const modeResponse = await fetch(`/api/analytics/retrieval-modes?${docParams}`);
            const modeData = await modeResponse.json();

            if (modeData.status === 'success') {
                this.renderRetrievalModeAnalytics(modeData.analytics);
            }

            // Load model comparison
            const modelResponse = await fetch(`/api/analytics/models?${docParams}`);
            const modelData = await modelResponse.json();

            if (modelData.status === 'success') {
                this.renderModelComparison(modelData.analytics);
            }

        } catch (error) {
            console.error('Error loading analytics:', error);
        }
    }

    renderDocumentAnalytics(analytics) {
        const summary = analytics.summary || {};
        
        document.getElementById('totalDocs').textContent = summary.total_documents || 0;
        document.getElementById('totalQueries').textContent = '-';
        document.getElementById('avgScore').textContent = '-';
        document.getElementById('avgResponseTime').textContent = '-';

        // Most retrieved
        const topRetrieved = analytics.most_retrieved || [];
        const retrievedContainer = document.getElementById('topRetrievedDocs');
        retrievedContainer.innerHTML = topRetrieved.slice(0, 10).map(doc => `
            <div class="ranking-item">
                <span class="title">${this.escapeHtml(doc.title || 'Untitled')}</span>
                <span class="count">${doc.total_retrievals}</span>
            </div>
        `).join('') || '<p class="empty-state">No data</p>';

        // Most cited
        const topCited = analytics.most_cited || [];
        const citedContainer = document.getElementById('topCitedDocs');
        citedContainer.innerHTML = topCited.slice(0, 10).map(doc => `
            <div class="ranking-item">
                <span class="title">${this.escapeHtml(doc.title || 'Untitled')}</span>
                <span class="count">${doc.total_citations}</span>
            </div>
        `).join('') || '<p class="empty-state">No data</p>';
    }

    renderRetrievalModeAnalytics(analytics) {
        const container = document.getElementById('retrievalModeStats');
        
        if (Object.keys(analytics).length === 0) {
            container.innerHTML = '<p class="empty-state">No data</p>';
            return;
        }

        const table = `
            <table>
                <thead>
                    <tr>
                        <th>Mode</th>
                        <th>Queries</th>
                        <th>Avg Response Time</th>
                        <th>Evaluations</th>
                        <th>Avg Score</th>
                    </tr>
                </thead>
                <tbody>
                    ${Object.entries(analytics).map(([mode, stats]) => `
                        <tr>
                            <td><strong>${mode}</strong></td>
                            <td>${stats.query_count}</td>
                            <td>${stats.avg_response_time_ms ? stats.avg_response_time_ms.toFixed(0) + 'ms' : '-'}</td>
                            <td>${stats.evaluation_count}</td>
                            <td>${stats.avg_overall_score ? stats.avg_overall_score.toFixed(1) : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        container.innerHTML = table;
    }

    renderModelComparison(analytics) {
        const container = document.getElementById('modelComparison');
        
        if (Object.keys(analytics).length === 0) {
            container.innerHTML = '<p class="empty-state">No data</p>';
            return;
        }

        const table = `
            <table>
                <thead>
                    <tr>
                        <th>Model</th>
                        <th>Queries</th>
                        <th>Avg Time</th>
                        <th>Avg Score</th>
                        <th>Avg Tokens</th>
                        <th>Total Cost</th>
                    </tr>
                </thead>
                <tbody>
                    ${Object.entries(analytics).map(([model, stats]) => `
                        <tr>
                            <td><strong>${model}</strong></td>
                            <td>${stats.query_count}</td>
                            <td>${stats.avg_response_time_ms ? stats.avg_response_time_ms.toFixed(0) + 'ms' : '-'}</td>
                            <td>${stats.avg_overall_score ? stats.avg_overall_score.toFixed(1) : '-'}</td>
                            <td>${stats.avg_tokens_out ? Math.round(stats.avg_tokens_out) : '-'}</td>
                            <td>${stats.total_cost ? '$' + stats.total_cost.toFixed(4) : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        container.innerHTML = table;
    }

    async loadEvaluations() {
        try {
            const params = new URLSearchParams({ limit: '50' });
            if (this.currentCollection) {
                params.append('collection', this.currentCollection);
            }

            const response = await fetch(`/api/query-runs?${params}`);
            const data = await response.json();

            if (data.status === 'success') {
                this.queryRuns = data.query_runs || [];
                this.renderQueryRuns(this.queryRuns);
            }
        } catch (error) {
            console.error('Error loading evaluations:', error);
        }
    }

    renderQueryRuns(queryRuns) {
        const container = document.getElementById('recentQueryRuns');
        
        if (queryRuns.length === 0) {
            container.innerHTML = '<p class="empty-state">No query runs found</p>';
            return;
        }

        container.innerHTML = queryRuns.map(qr => `
            <div class="query-run-item">
                <div class="query-run-header">
                    <div>
                        <div class="query-text">${this.escapeHtml(qr.user_query)}</div>
                        <div class="query-meta">
                            ${new Date(qr.created_at).toLocaleString()} • 
                            ${qr.retrieval_mode || 'unknown'} • 
                            ${qr.llm_model || 'unknown'}
                        </div>
                    </div>
                    <div class="query-actions">
                        <button class="btn btn-sm btn-primary" onclick="dashboard.evaluateQuery('${qr.id}')">
                            ⭐ Evaluate
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    showCreateDocModal() {
        document.getElementById('createDocModal').classList.add('active');
    }

    async createDocument(form) {
        const formData = new FormData(form);
        const data = {
            collection: this.currentCollection || 'default',
            title: formData.get('title'),
            document_type: formData.get('document_type'),
            author: formData.get('author'),
            year: formData.get('year') ? parseInt(formData.get('year')) : null,
            doi: formData.get('doi'),
            abstract: formData.get('abstract'),
            notes: formData.get('notes')
        };

        try {
            const response = await fetch('/api/documents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.status === 'success') {
                document.getElementById('createDocModal').classList.remove('active');
                form.reset();
                this.loadDocuments();
                this.showSuccess('Document created successfully');
            } else {
                this.showError(result.message || 'Failed to create document');
            }
        } catch (error) {
            console.error('Error creating document:', error);
            this.showError('Error creating document');
        }
    }

    evaluateQuery(queryRunId) {
        const queryRun = this.queryRuns.find(qr => qr.id === queryRunId);
        if (!queryRun) return;

        const modal = document.getElementById('evaluationModal');
        const context = document.getElementById('queryContext');
        
        context.innerHTML = `
            <p><strong>Query:</strong> ${this.escapeHtml(queryRun.user_query)}</p>
            <p><strong>Model:</strong> ${queryRun.llm_model || 'unknown'}</p>
            <p><strong>Time:</strong> ${new Date(queryRun.created_at).toLocaleString()}</p>
        `;

        document.querySelector('input[name="query_run_id"]').value = queryRunId;
        modal.classList.add('active');
    }

    async submitEvaluation(form) {
        const formData = new FormData(form);
        const data = {
            query_run_id: formData.get('query_run_id'),
            overall_score: parseInt(formData.get('overall_score')) || null,
            accuracy_score: parseInt(formData.get('accuracy_score')) || null,
            relevance_score: parseInt(formData.get('relevance_score')) || null,
            completeness_score: parseInt(formData.get('completeness_score')) || null,
            hallucination_flag: formData.get('hallucination_flag') === 'on',
            feedback_text: formData.get('feedback_text')
        };

        try {
            const response = await fetch('/api/evaluations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.status === 'success') {
                document.getElementById('evaluationModal').classList.remove('active');
                form.reset();
                this.setStarRating(0);
                this.showSuccess('Evaluation submitted successfully');
            } else {
                this.showError(result.message || 'Failed to submit evaluation');
            }
        } catch (error) {
            console.error('Error submitting evaluation:', error);
            this.showError('Error submitting evaluation');
        }
    }

    setStarRating(value) {
        document.querySelectorAll('.star').forEach((star, index) => {
            star.classList.toggle('active', index < value);
        });
        document.querySelector('input[name="overall_score"]').value = value;
    }

    async loadCollectionsGrid() {
        try {
            console.log('Loading collections...');
            const response = await fetch('/collections');
            const data = await response.json();
            console.log('Collections data:', data);
            
            if (data.collections) {
                this.collections = data.collections;
                console.log('Rendering', data.collections.length, 'collections');
                this.renderCollections(data.collections);
            } else {
                console.warn('No collections in response');
                document.getElementById('collectionsGrid').innerHTML = '<div class="empty-state"><h3>No Collections</h3><p>Upload some documents to create collections</p></div>';
            }
        } catch (error) {
            console.error('Error loading collections:', error);
            document.getElementById('collectionsGrid').innerHTML = '<div class="empty-state"><h3>Error Loading Collections</h3><p>' + error.message + '</p></div>';
        }
    }

    renderCollections(collections) {
        const grid = document.getElementById('collectionsGrid');
        
        if (collections.length === 0) {
            grid.innerHTML = '<div class="empty-state"><h3>No Collections</h3><p>Create your first collection to get started</p></div>';
            return;
        }

        grid.innerHTML = collections.map(coll => {
            const hasImage = coll.image || coll.image_url;
            const imageSection = hasImage
                ? `<div class="collection-card-image">
                     <img src="${this.escapeHtml(coll.image_url || coll.image || `/collections/${coll.name}/image`)}" alt="${this.escapeHtml(coll.display_name || coll.name)}">
                   </div>`
                : `<div class="collection-card-image">📁</div>`;
            
            return `
                <div class="collection-card" onclick="dashboard.openCollection('${this.escapeHtml(coll.name)}')">
                    ${imageSection}
                    <div class="collection-card-content">
                        <h3>${this.escapeHtml(coll.display_name || coll.name)}</h3>
                        <p>${this.escapeHtml(coll.description || 'No description')}</p>
                        <div class="collection-stats">
                            <div class="collection-stat">
                                <strong>${coll.file_count || 0}</strong> documents
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    showCreateCollectionModal() {
        document.getElementById('createCollectionModal').classList.add('active');
    }

    async createCollection(form) {
        const formData = new FormData(form);

        try {
            console.log('Submitting collection form...');
            const response = await fetch('/collections', {
                method: 'POST',
                body: formData
            });

            console.log('Response status:', response.status);
            const result = await response.json();
            console.log('Response data:', result);

            if (response.ok && result.status === 'success') {
                document.getElementById('createCollectionModal').classList.remove('active');
                form.reset();
                this.showSuccess('Collection created successfully');
                await this.loadCollectionsGrid();
            } else {
                // Show the actual error from the server
                const errorMsg = result.detail || result.message || 'Failed to create collection';
                console.error('Server error:', errorMsg);
                this.showError(errorMsg);
            }
        } catch (error) {
            console.error('Error creating collection:', error);
            this.showError('Error creating collection: ' + error.message);
        }
    }

    async openCollection(collectionName) {
        this.currentCollection = collectionName;
        
        // Load collection metadata
        await this.loadCollectionMetadata(collectionName);
        
        // Load collection documents
        await this.loadCollectionDocuments(collectionName);
        
        // Show modal
        document.getElementById('uploadPdfCollection').value = collectionName;
        document.getElementById('collectionDetailModal').classList.add('active');
        
        // Switch to documents tab by default
        document.querySelectorAll('.collection-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.collection-tab-pane').forEach(p => p.classList.remove('active'));
        document.querySelector('.collection-tab-btn[data-tab="documents"]').classList.add('active');
        document.getElementById('collectionDocumentsTab').classList.add('active');
    }

    async loadCollectionMetadata(collectionName) {
        try {
            const response = await fetch('/collections');
            const data = await response.json();
            
            if (data.status === 'success') {
                const collection = data.collections.find(c => c.name === collectionName);
                if (collection) {
                    // Store collection data for later use
                    this.currentCollectionData = collection;
                    
                    // Update modal title
                    document.getElementById('collectionDetailTitle').textContent = collection.display_name || collectionName;
                    document.getElementById('collectionDetailDescription').textContent = collection.description || 'Collection: ' + collectionName;
                }
            }
        } catch (error) {
            console.error('Error loading collection metadata:', error);
        }
    }

    async loadCollectionSettings(collectionName) {
        if (!this.currentCollectionData) return;
        
        const collection = this.currentCollectionData;
        
        // Populate form fields
        document.getElementById('settingsCollectionName').value = collection.name;
        document.getElementById('settingsDisplayName').value = collection.display_name || collection.name;
        document.getElementById('settingsDescription').value = collection.description || '';
        
        // Show current image if exists
        const imagePreview = document.getElementById('currentImagePreview');
        const imageImg = document.getElementById('currentImageImg');
        
        const hasImage = collection.image || collection.image_url;
        if (hasImage) {
            imageImg.src = collection.image_url || collection.image || `/collections/${collection.name}/image`;
            imagePreview.style.display = 'block';
        } else {
            imagePreview.style.display = 'none';
        }
    }

    async saveCollectionSettings(form) {
        const formData = new FormData(form);
        const collectionName = formData.get('collection_name');
        
        if (!collectionName) {
            this.showError('Collection name is missing');
            return;
        }
        
        try {
            console.log('Saving collection settings...');
            const response = await fetch(`/collections/${collectionName}`, {
                method: 'PUT',
                body: formData
            });
            
            const result = await response.json();
            console.log('Save response:', result);
            
            if (response.ok && result.status === 'success') {
                this.showSuccess('Collection settings saved successfully');
                
                // Reload collections grid and metadata
                await this.loadCollectionsGrid();
                await this.loadCollectionMetadata(result.new_name || collectionName);
                
                // Update current collection name if it changed
                if (result.new_name && result.new_name !== collectionName) {
                    this.currentCollection = result.new_name;
                }
            } else {
                const errorMsg = result.detail || result.message || 'Failed to save settings';
                this.showError(errorMsg);
            }
        } catch (error) {
            console.error('Error saving collection settings:', error);
            this.showError('Error saving settings: ' + error.message);
        }
    }

    async loadCollectionDocuments(collection) {
        try {
            const [docsResp, statsResp] = await Promise.all([
                fetch(`/api/documents?${new URLSearchParams({ collection, limit: '100' })}`),
                fetch(`/collections/${encodeURIComponent(collection)}/stats`),
            ]);
            const data = await docsResp.json();
            const stats = statsResp.ok ? await statsResp.json() : null;

            if (data.status === 'success') {
                this.renderCollectionDocuments(data.documents || []);
                const recordCount = stats ? stats.record_count : data.documents.length;
                const fileCount = stats ? stats.disk_file_count : '?';
                document.getElementById('collectionDocCount').textContent =
                    `${recordCount} records · ${fileCount} files`;
            }
        } catch (error) {
            console.error('Error loading collection documents:', error);
        }
    }

    renderCollectionDocuments(documents) {
        const tbody = document.getElementById('collectionDocumentsBody');
        
        if (documents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No documents in this collection</td></tr>';
            return;
        }

        tbody.innerHTML = documents.map(doc => {
            const title = this.escapeHtml(doc.title || 'Untitled');
            const needsUpload = !doc.pdf_attached || doc.ingestion_status === 'failed' || doc.ingestion_status === 'not_uploaded';
            const uploadBtn = needsUpload
                ? `<button class="btn-icon btn-icon--success" title="Upload PDF" onclick="dashboard.showUploadPdfForDocument(${doc.id}, '${title}')">${ICON_UPLOAD}</button>`
                : '';
            return `
                <tr>
                    <td class="cell-truncate"><div class="cell-inner cell-inner--bold" title="${title}">${title}</div></td>
                    <td class="cell-truncate"><div class="cell-inner">${this.escapeHtml(doc.document_type || '-')}</div></td>
                    <td class="cell-truncate"><div class="cell-inner">${this.escapeHtml(doc.author || '-')}</div></td>
                    <td>${doc.year || '-'}</td>
                    <td>${doc.pdf_attached ? '✓' : '–'}</td>
                    <td><span class="status-badge status-${doc.ingestion_status}">${doc.ingestion_status || 'unknown'}</span></td>
                    <td class="cell-actions">
                        ${uploadBtn}
                        <button class="btn-icon btn-icon--primary" title="Edit" onclick="dashboard.editDocument(${doc.id})">${ICON_EDIT}</button>
                        <button class="btn-icon btn-icon--danger" title="Delete" onclick="dashboard.deleteDocument(${doc.id}, '${title}')">${ICON_DELETE}</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    async uploadPdf(form) {
        const formData = new FormData(form);
        const collection = formData.get('collection');
        
        try {
            document.getElementById('uploadProgress').style.display = 'block';
            document.getElementById('uploadProgressText').textContent = 'Uploading...';
            document.getElementById('uploadProgressFill').style.width = '50%';

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.status === 'success') {
                document.getElementById('uploadProgressFill').style.width = '100%';
                document.getElementById('uploadProgressText').textContent = 'Upload complete!';
                
                setTimeout(() => {
                    document.getElementById('uploadPdfModal').classList.remove('active');
                    document.getElementById('uploadProgress').style.display = 'none';
                    document.getElementById('uploadProgressFill').style.width = '0%';
                    form.reset();
                    this.showSuccess('PDF uploaded successfully');
                    this.loadCollectionDocuments(collection);
                }, 1000);
            } else {
                throw new Error(result.message || 'Upload failed');
            }
        } catch (error) {
            console.error('Error uploading PDF:', error);
            document.getElementById('uploadProgress').style.display = 'none';
            this.showError('Error uploading PDF');
        }
    }

    showUploadPdfForDocument(documentId, documentTitle) {
        // Store the document ID for later use
        this.currentDocumentId = documentId;
        
        // Create a simple file input dialog
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (file) {
                await this.uploadPdfForDocument(documentId, file, documentTitle);
            }
        };
        input.click();
    }

    async uploadPdfForDocument(documentId, file, documentTitle) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            this.showStatus('uploadStatus', `Uploading PDF for "${documentTitle}"...`, 'info');
            
            const response = await fetch(`/api/documents/attach-pdf/${documentId}`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                this.showSuccess(`PDF attached successfully! Ingestion status: ${result.ingestion_status}`);
                // Reload documents to show updated status
                await this.loadDocuments();
            } else {
                const errorMsg = result.detail || result.message || 'Failed to attach PDF';
                this.showError(errorMsg);
            }
        } catch (error) {
            console.error('Error uploading PDF:', error);
            this.showError('Error uploading PDF: ' + error.message);
        }
    }

    async editDocument(id) {
        let overlay = null;
        try {
            // Show loading indicator
            overlay = document.createElement('div');
            overlay.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;';
            overlay.innerHTML = '<div style="background: white; padding: 40px; border-radius: 8px; text-align: center;"><p>Loading document...</p></div>';
            document.body.appendChild(overlay);
            
            // Fetch document from API
            const response = await fetch(`/api/documents/${id}`);
            if (!response.ok) {
                throw new Error('Failed to load document from server');
            }
            const result = await response.json();
            
            if (result.status !== 'success' || !result.document) {
                throw new Error('Document not found in database');
            }
            
            const doc = result.document;
            
            // Remove loading indicator
            overlay.remove();
            
            // Create edit form
            const form = `
                <div style="padding: 20px;">
                    <h2>Edit Document</h2>
                    <form id="editDocForm" style="margin-top: 20px;">
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Title *</label>
                            <input type="text" name="title" value="${this.escapeHtml(doc.title || '')}" required style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Type</label>
                            <select name="document_type" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                                <option value="">Select type...</option>
                                <option value="journal_article" ${doc.document_type === 'journal_article' ? 'selected' : ''}>Journal Article</option>
                                <option value="conference_paper" ${doc.document_type === 'conference_paper' ? 'selected' : ''}>Conference Paper</option>
                                <option value="book" ${doc.document_type === 'book' ? 'selected' : ''}>Book</option>
                                <option value="book_chapter" ${doc.document_type === 'book_chapter' ? 'selected' : ''}>Book Chapter</option>
                                <option value="thesis" ${doc.document_type === 'thesis' ? 'selected' : ''}>Thesis</option>
                                <option value="report" ${doc.document_type === 'report' ? 'selected' : ''}>Report</option>
                                <option value="preprint" ${doc.document_type === 'preprint' ? 'selected' : ''}>Preprint</option>
                            </select>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Author</label>
                            <input type="text" name="author" value="${this.escapeHtml(doc.author || '')}" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Year</label>
                            <input type="number" name="year" value="${doc.year || ''}" min="1900" max="2100" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">DOI</label>
                            <input type="text" name="doi" value="${this.escapeHtml(doc.doi || '')}" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Abstract</label>
                            <textarea name="abstract" rows="4" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">${this.escapeHtml(doc.abstract || '')}</textarea>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Notes</label>
                            <textarea name="notes" rows="3" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">${this.escapeHtml(doc.notes || '')}</textarea>
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <button type="submit" class="btn btn-primary">Save Changes</button>
                            <button type="button" onclick="this.closest('div').parentElement.parentElement.parentElement.remove()" class="btn btn-secondary">Cancel</button>
                        </div>
                    </form>
                </div>
            `;
            
            // Create new overlay for the form
            overlay = document.createElement('div');
            overlay.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;';
            overlay.innerHTML = `<div style="background: white; border-radius: 8px; max-width: 600px; max-height: 80vh; overflow-y: auto;">${form}</div>`;
            document.body.appendChild(overlay);
            
            // Click outside to close
            overlay.onclick = (e) => { 
                if (e.target === overlay) {
                    overlay.remove();
                }
            };
            
            // Handle form submission
            document.getElementById('editDocForm').onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = {
                    title: formData.get('title'),
                    document_type: formData.get('document_type') || null,
                    author: formData.get('author') || null,
                    year: formData.get('year') ? parseInt(formData.get('year')) : null,
                    doi: formData.get('doi') || null,
                    abstract: formData.get('abstract') || null,
                    notes: formData.get('notes') || null
                };
                
                try {
                    const response = await fetch(`/api/documents/${id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok && result.status === 'success') {
                        this.showSuccess('Document updated successfully');
                        overlay.remove();
                        
                        // Reload documents in main tab
                        await this.loadDocuments();
                        
                        // Also reload collection documents if we're viewing a collection
                        if (this.currentCollection) {
                            await this.loadCollectionDocuments(this.currentCollection);
                        }
                    } else {
                        this.showError(result.message || 'Failed to update document');
                    }
                } catch (error) {
                    console.error('Error updating document:', error);
                    this.showError('Error updating document: ' + error.message);
                }
            };
        } catch (error) {
            console.error('Error editing document:', error);
            this.showError('Error loading document: ' + error.message);
            
            // Remove overlay if it exists
            if (overlay && overlay.parentNode) {
                overlay.remove();
            }
        }
    }

    async deleteDocument(id, title) {
        if (!confirm(`Are you sure you want to delete "${title}"?\n\nThis will remove the document and all its chunks from the database.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/documents/${id}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                this.showSuccess('Document deleted successfully');
                
                // Reload documents in main tab
                await this.loadDocuments();
                
                // Also reload collection documents if we're viewing a collection
                if (this.currentCollection) {
                    await this.loadCollectionDocuments(this.currentCollection);
                }
            } else {
                this.showError(result.message || 'Failed to delete document');
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            this.showError('Error deleting document: ' + error.message);
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showSuccess(message) {
        alert(message); // Replace with better notification system
    }

    showError(message) {
        alert('Error: ' + message); // Replace with better notification system
    }
}

// Initialize dashboard
const dashboard = new Dashboard();
