// Document Manager - Handles the unified Add Document modal and document operations

class DocumentManager {
  constructor() {
    this.modal = document.getElementById('addDocumentModal');
    this.currentCollection = null;
    this.initializeEventListeners();
    this.initializeCollectionListeners();
  }

  initializeEventListeners() {
    // Tab switching
    document.getElementById('tabUploadPdf')?.addEventListener('click', () => this.switchTab('uploadPdf'));
    document.getElementById('tabAddManual')?.addEventListener('click', () => this.switchTab('addManual'));
    document.getElementById('tabImportCsv')?.addEventListener('click', () => this.switchTab('importCsv'));
    document.getElementById('tabImportRis')?.addEventListener('click', () => this.switchTab('importRis'));

    // Close button
    document.getElementById('closeAddDocumentBtn')?.addEventListener('click', () => this.closeModal());

    // Form submissions
    document.getElementById('uploadPdfForm')?.addEventListener('submit', (e) => this.handleUploadPdf(e));
    document.getElementById('addManualForm')?.addEventListener('submit', (e) => this.handleAddManual(e));
    document.getElementById('importCsvForm')?.addEventListener('submit', (e) => this.handleImportCsv(e));
    document.getElementById('importRisForm')?.addEventListener('submit', (e) => this.handleImportRis(e, 'modal'));

    // Close modal when clicking overlay
    this.modal?.querySelector('.modal__overlay')?.addEventListener('click', () => this.closeModal());
  }

  initializeCollectionListeners() {
    // Collection-specific listeners
    const addBtn = document.getElementById('addDocumentToCollectionBtn');
    if (addBtn) {
      addBtn.addEventListener('click', () => this.showCollectionInterface());
    }

    // Collection tab switching
    document.getElementById('tabCollectionUploadPdf')?.addEventListener('click', () => this.switchCollectionTab('uploadPdf'));
    document.getElementById('tabCollectionAddManual')?.addEventListener('click', () => this.switchCollectionTab('addManual'));
    document.getElementById('tabCollectionImportCsv')?.addEventListener('click', () => this.switchCollectionTab('importCsv'));
    document.getElementById('tabCollectionImportRis')?.addEventListener('click', () => this.switchCollectionTab('importRis'));

    // Collection form submissions
    document.getElementById('collectionUploadPdfForm')?.addEventListener('submit', (e) => this.handleCollectionUploadPdf(e));
    document.getElementById('collectionAddManualForm')?.addEventListener('submit', (e) => this.handleCollectionAddManual(e));
    document.getElementById('collectionImportCsvForm')?.addEventListener('submit', (e) => this.handleCollectionImportCsv(e));
    document.getElementById('collectionImportRisForm')?.addEventListener('submit', (e) => this.handleImportRis(e, 'collection'));
  }

  showCollectionInterface() {
    const interface = document.getElementById('addDocumentInterface');
    if (interface) {
      interface.style.display = 'block';
      this.switchCollectionTab('uploadPdf');
      this.resetCollectionForms();
    }
  }

  switchCollectionTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('#addDocumentInterface .docs-tab').forEach(tab => tab.classList.remove('docs-tab--active'));
    document.getElementById(`tabCollection${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`)?.classList.add('docs-tab--active');

    // Update tab content
    document.getElementById('collectionUploadPdfTab').style.display = tabName === 'uploadPdf' ? 'block' : 'none';
    document.getElementById('collectionAddManualTab').style.display = tabName === 'addManual' ? 'block' : 'none';
    document.getElementById('collectionImportCsvTab').style.display = tabName === 'importCsv' ? 'block' : 'none';
    document.getElementById('collectionImportRisTab').style.display = tabName === 'importRis' ? 'block' : 'none';
  }

  resetCollectionForms() {
    document.getElementById('collectionUploadPdfForm')?.reset();
    document.getElementById('collectionAddManualForm')?.reset();
    document.getElementById('collectionImportCsvForm')?.reset();
    
    // Hide progress/status elements
    document.getElementById('collectionUploadPdfProgressWrap').style.display = 'none';
    document.getElementById('collectionUploadPdfStatus').textContent = '';
    document.getElementById('collectionAddManualStatus').textContent = '';
    document.getElementById('collectionImportCsvStatus').textContent = '';
    document.getElementById('collectionImportCsvResults').style.display = 'none';
    document.getElementById('collectionImportRisForm')?.reset();
    document.getElementById('collectionImportRisStatus').textContent = '';
    document.getElementById('collectionImportRisResults').style.display = 'none';
  }

  async handleCollectionUploadPdf(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('collectionUploadPdfFile');
    const file = fileInput.files[0];
    const collection = document.getElementById('editCollectionId')?.value || this.currentCollection;
    
    if (!file) {
      this.showStatus('collectionUploadPdfStatus', 'Please select a PDF file', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('collection', collection);

    this.showProgress('collectionUploadPdf', 'Uploading...', 0);

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (result.status === 'success') {
        this.showProgress('collectionUploadPdf', 'Upload complete!', 100);
        this.showStatus('collectionUploadPdfStatus', 'Document uploaded and indexed successfully!', 'success');
        
        setTimeout(() => {
          document.getElementById('addDocumentInterface').style.display = 'none';
          this.loadCollectionDocuments(collection);
        }, 1500);
      } else {
        this.showStatus('collectionUploadPdfStatus', result.message || 'Upload failed', 'error');
        document.getElementById('collectionUploadPdfProgressWrap').style.display = 'none';
      }
    } catch (error) {
      console.error('Upload error:', error);
      this.showStatus('collectionUploadPdfStatus', 'Upload failed: ' + error.message, 'error');
      document.getElementById('collectionUploadPdfProgressWrap').style.display = 'none';
    }
  }

  async handleCollectionAddManual(e) {
    e.preventDefault();

    const title = document.getElementById('collectionManualTitle').value.trim();
    const collection = document.getElementById('editCollectionId')?.value || this.currentCollection;
    
    if (!title) {
      this.showStatus('collectionAddManualStatus', 'Title is required', 'error');
      return;
    }

    const tags = document.getElementById('collectionManualTags').value.trim();
    const payload = {
      collection: collection,
      title: title,
      author: document.getElementById('collectionManualAuthor').value.trim() || null,
      year: document.getElementById('collectionManualYear').value ? parseInt(document.getElementById('collectionManualYear').value) : null,
      document_type: document.getElementById('collectionManualDocType').value || null,
      doi: document.getElementById('collectionManualDoi').value.trim() || null,
      abstract: document.getElementById('collectionManualAbstract').value.trim() || null,
      notes: document.getElementById('collectionManualNotes').value.trim() || null,
      tags: tags ? tags.split(',').map(t => t.trim()).filter(t => t) : null,
      apa7_reference: document.getElementById('collectionManualApa7').value.trim() || null
    };

    this.showStatus('collectionAddManualStatus', 'Creating document...', 'info');

    try {
      const response = await fetch('/api/documents/add-manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await response.json();

      if (result.status === 'success') {
        this.showStatus('collectionAddManualStatus', 'Document created successfully!', 'success');
        
        setTimeout(() => {
          document.getElementById('addDocumentInterface').style.display = 'none';
          this.loadCollectionDocuments(collection);
        }, 1500);
      } else {
        this.showStatus('collectionAddManualStatus', result.message || 'Failed to create document', 'error');
      }
    } catch (error) {
      console.error('Create document error:', error);
      this.showStatus('collectionAddManualStatus', 'Failed to create document: ' + error.message, 'error');
    }
  }

  async handleCollectionImportCsv(e) {
    e.preventDefault();

    const fileInput = document.getElementById('collectionImportCsvFile');
    const file = fileInput.files[0];
    const collection = document.getElementById('editCollectionId')?.value || this.currentCollection;

    if (!file) {
      this.showStatus('collectionImportCsvStatus', 'Please select a CSV file', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('collection', collection);

    this.showStatus('collectionImportCsvStatus', 'Importing documents...', 'info');

    try {
      const response = await fetch('/api/documents/bulk-import', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (result.status === 'success' || result.imported_count > 0) {
        this.showStatus('collectionImportCsvStatus', '', '');
        this.showImportResults(result, 'collection');
        
        setTimeout(() => {
          document.getElementById('addDocumentInterface').style.display = 'none';
          this.loadCollectionDocuments(collection);
        }, 3000);
      } else {
        const errMsg = result.detail || result.message || result.errors?.[0]?.error || 'Import failed';
        this.showStatus('collectionImportCsvStatus', errMsg, 'error');
      }
    } catch (error) {
      console.error('Import error:', error);
      this.showStatus('collectionImportCsvStatus', 'Import failed: ' + error.message, 'error');
    }
  }

  async loadCollectionDocuments(collection) {
    try {
      const response = await fetch(`/api/documents?collection=${encodeURIComponent(collection)}`);
      const result = await response.json();
      
      if (result.status === 'success') {
        this.renderCollectionDocuments(result.documents || []);
      }
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  }

  renderCollectionDocuments(documents) {
    const container = document.getElementById('collectionDocumentsList');
    if (!container) return;

    if (documents.length === 0) {
      container.innerHTML = '<p class="hint">No documents yet. Click "+ Add Document" to get started.</p>';
      return;
    }

    container.innerHTML = documents.map(doc => `
      <div class="doc-item" style="padding: 16px; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 12px;">
        <div class="doc-item-header">
          <div class="doc-item-title">
            <strong>${doc.title || 'Untitled'}</strong>
            ${DocumentManager.createStatusBadge(doc.ingestion_status || 'unknown')}
            ${doc.metadata_complete ? '<span class="metadata-complete-badge">✓ Complete</span>' : ''}
          </div>
          <div class="doc-item-actions">
            ${!doc.pdf_attached ? DocumentManager.createAttachPdfButton(doc.id) : ''}
            <button class="btn-sm" onclick="documentManager.editDocumentMetadata(${doc.id})">Edit</button>
          </div>
        </div>
        <div style="margin-top: 8px; font-size: 13px; color: var(--text-light);">
          ${doc.author ? `<div>Author: ${doc.author}</div>` : ''}
          ${doc.year ? `<div>Year: ${doc.year}</div>` : ''}
          ${doc.document_type ? `<div>Type: ${doc.document_type}</div>` : ''}
          ${doc.doi ? `<div>DOI: ${doc.doi}</div>` : ''}
        </div>
      </div>
    `).join('');
  }

  editDocumentMetadata(documentId) {
    // TODO: Implement edit functionality
    alert('Edit functionality coming soon! Document ID: ' + documentId);
  }

  openModal(collection) {
    this.currentCollection = collection;
    this.modal.style.display = 'block';
    this.switchTab('uploadPdf'); // Default to upload tab
    this.resetForms();
  }

  closeModal() {
    this.modal.style.display = 'none';
    this.resetForms();
  }

  switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.docs-tab').forEach(tab => tab.classList.remove('docs-tab--active'));
    document.getElementById(`tab${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`)?.classList.add('docs-tab--active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.style.display = 'none');
    document.getElementById(`${tabName}Tab`).style.display = 'block';
  }

  resetForms() {
    document.getElementById('uploadPdfForm')?.reset();
    document.getElementById('addManualForm')?.reset();
    document.getElementById('importCsvForm')?.reset();
    
    // Hide progress/status elements
    document.getElementById('uploadPdfProgressWrap').style.display = 'none';
    document.getElementById('uploadPdfStatus').textContent = '';
    document.getElementById('addManualStatus').textContent = '';
    document.getElementById('importCsvStatus').textContent = '';
    document.getElementById('importCsvResults').style.display = 'none';
    document.getElementById('importRisForm')?.reset();
    document.getElementById('importRisStatus').textContent = '';
    document.getElementById('importRisResults').style.display = 'none';
  }

  async handleUploadPdf(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('uploadPdfFile');
    const file = fileInput.files[0];
    
    if (!file) {
      this.showStatus('uploadPdfStatus', 'Please select a PDF file', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('collection', this.currentCollection);

    this.showProgress('uploadPdf', 'Uploading...', 0);

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (result.status === 'success') {
        this.showProgress('uploadPdf', 'Upload complete!', 100);
        this.showStatus('uploadPdfStatus', 'Document uploaded and indexed successfully!', 'success');
        
        setTimeout(() => {
          this.closeModal();
          window.location.reload(); // Refresh to show new document
        }, 1500);
      } else {
        this.showStatus('uploadPdfStatus', result.message || 'Upload failed', 'error');
        document.getElementById('uploadPdfProgressWrap').style.display = 'none';
      }
    } catch (error) {
      console.error('Upload error:', error);
      this.showStatus('uploadPdfStatus', 'Upload failed: ' + error.message, 'error');
      document.getElementById('uploadPdfProgressWrap').style.display = 'none';
    }
  }

  async handleAddManual(e) {
    e.preventDefault();

    const title = document.getElementById('manualTitle').value.trim();
    if (!title) {
      this.showStatus('addManualStatus', 'Title is required', 'error');
      return;
    }

    const tags = document.getElementById('manualTags').value.trim();
    const payload = {
      collection: this.currentCollection,
      title: title,
      author: document.getElementById('manualAuthor').value.trim() || null,
      year: document.getElementById('manualYear').value ? parseInt(document.getElementById('manualYear').value) : null,
      document_type: document.getElementById('manualDocType').value || null,
      doi: document.getElementById('manualDoi').value.trim() || null,
      abstract: document.getElementById('manualAbstract').value.trim() || null,
      notes: document.getElementById('manualNotes').value.trim() || null,
      tags: tags ? tags.split(',').map(t => t.trim()).filter(t => t) : null,
      apa7_reference: document.getElementById('manualApa7').value.trim() || null
    };

    this.showStatus('addManualStatus', 'Creating document...', 'info');

    try {
      const response = await fetch('/api/documents/add-manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await response.json();

      if (result.status === 'success') {
        this.showStatus('addManualStatus', 'Document created successfully!', 'success');
        
        setTimeout(() => {
          this.closeModal();
          window.location.reload(); // Refresh to show new document
        }, 1500);
      } else {
        this.showStatus('addManualStatus', result.message || 'Failed to create document', 'error');
      }
    } catch (error) {
      console.error('Create document error:', error);
      this.showStatus('addManualStatus', 'Failed to create document: ' + error.message, 'error');
    }
  }

  async handleImportCsv(e) {
    e.preventDefault();

    const fileInput = document.getElementById('importCsvFile');
    const file = fileInput.files[0];

    if (!file) {
      this.showStatus('importCsvStatus', 'Please select a CSV file', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('collection', this.currentCollection);

    this.showStatus('importCsvStatus', 'Importing documents...', 'info');

    try {
      const response = await fetch('/api/documents/bulk-import', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (result.status === 'success' || result.imported_count > 0) {
        this.showStatus('importCsvStatus', '', '');
        this.showImportResults(result);
        
        if (result.error_count === 0) {
          setTimeout(() => {
            this.closeModal();
            window.location.reload(); // Refresh to show new documents
          }, 3000);
        }
      } else {
        const errMsg = result.detail || result.message || result.errors?.[0]?.error || 'Import failed';
        this.showStatus('importCsvStatus', errMsg, 'error');
      }
    } catch (error) {
      console.error('Import error:', error);
      this.showStatus('importCsvStatus', 'Import failed: ' + error.message, 'error');
    }
  }

  async handleImportRis(e, context) {
    e.preventDefault();
    const isCollection = context === 'collection';
    const prefix = isCollection ? 'collectionImportRis' : 'importRis';
    const fileInput = document.getElementById(`${prefix}File`);
    const file = fileInput?.files[0];
    const collection = isCollection
      ? (document.getElementById('editCollectionId')?.value || this.currentCollection)
      : this.currentCollection;

    if (!file) {
      this.showStatus(`${prefix}Status`, 'Please select a RIS file', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('collection', collection);

    this.showStatus(`${prefix}Status`, 'Importing records...', 'info');

    try {
      const response = await fetch('/api/documents/import-ris', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (result.status === 'queued' || result.queued_count > 0) {
        this.showStatus(`${prefix}Status`, '', '');
        const resultsDiv = document.getElementById(`${prefix}Results`);
        const successCount = document.getElementById(`${prefix}SuccessCount`);
        const errorCount = document.getElementById(`${prefix}ErrorCount`);
        const errorList = document.getElementById(`${prefix}ErrorList`);
        if (successCount) successCount.textContent = result.queued_count || 0;
        if (errorCount) errorCount.textContent = result.error_count || 0;
        if (errorList) {
          errorList.innerHTML = (result.errors || []).map(err =>
            `<div class="error-item">${err.title || 'Row'}: ${err.error}</div>`
          ).join('');
        }
        if (resultsDiv) resultsDiv.style.display = 'block';
        if ((result.error_count || 0) === 0) {
          setTimeout(() => window.location.reload(), 3000);
        }
      } else {
        const errMsg = result.detail || result.message || 'Import failed';
        this.showStatus(`${prefix}Status`, errMsg, 'error');
      }
    } catch (error) {
      console.error('RIS import error:', error);
      this.showStatus(`${prefix}Status`, 'Import failed: ' + error.message, 'error');
    }
  }

  showProgress(prefix, text, percent) {
    const progressWrap = document.getElementById(`${prefix}ProgressWrap`);
    const progressText = document.getElementById(`${prefix}ProgressText`);
    const progressPct = document.getElementById(`${prefix}ProgressPct`);
    const progressBar = document.getElementById(`${prefix}ProgressBar`);

    progressWrap.style.display = 'block';
    progressText.textContent = text;
    progressPct.textContent = `${percent}%`;
    progressBar.style.width = `${percent}%`;
  }

  showStatus(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = 'status';
    if (type === 'error') element.classList.add('status--error');
    if (type === 'success') element.classList.add('status--success');
    if (type === 'info') element.classList.add('status--info');
  }

  showImportResults(result, context = 'modal') {
    const prefix = context === 'collection' ? 'collection' : '';
    const resultsDiv = document.getElementById(`${prefix}ImportCsvResults`);
    const successCount = document.getElementById(`${prefix}ImportSuccessCount`);
    const errorCount = document.getElementById(`${prefix}ImportErrorCount`);
    const errorList = document.getElementById(`${prefix}ImportErrorList`);

    if (successCount) successCount.textContent = result.imported_count || 0;
    if (errorCount) errorCount.textContent = result.error_count || 0;

    if (errorList) {
      if (result.errors && result.errors.length > 0) {
        errorList.innerHTML = result.errors.map(err => 
          `<div class="error-item">Row ${err.row}: ${err.error}</div>`
        ).join('');
      } else {
        errorList.innerHTML = '';
      }
    }

    if (resultsDiv) resultsDiv.style.display = 'block';
  }

  // Helper function to create status badge HTML
  static createStatusBadge(status) {
    const statusClass = `status-badge--${status.replace('_', '-')}`;
    const statusText = status.replace('_', ' ');
    return `<span class="status-badge ${statusClass}">${statusText}</span>`;
  }

  // Helper function to create attach PDF button HTML
  static createAttachPdfButton(documentId) {
    return `
      <button class="btn-attach-pdf" onclick="documentManager.attachPdf(${documentId})">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
        </svg>
        Attach PDF
      </button>
    `;
  }

  async attachPdf(documentId) {
    // Create a file input dynamically
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf';
    
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await fetch(`/api/documents/attach-pdf/${documentId}`, {
          method: 'POST',
          body: formData
        });

        const result = await response.json();

        if (result.status === 'success') {
          alert('PDF attached successfully! The document will be processed.');
          window.location.reload();
        } else {
          alert('Failed to attach PDF: ' + (result.message || 'Unknown error'));
        }
      } catch (error) {
        console.error('Attach PDF error:', error);
        alert('Failed to attach PDF: ' + error.message);
      }
    };

    input.click();
  }
}

// Initialize document manager when DOM is ready
let documentManager;
document.addEventListener('DOMContentLoaded', () => {
  documentManager = new DocumentManager();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DocumentManager;
}
