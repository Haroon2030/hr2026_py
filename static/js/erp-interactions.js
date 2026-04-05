/**
 * AdminDek – HR Pro | ERP Interactions Module
 * Provides keyboard shortcuts, instant search, auto-save, and enhanced UX
 * Version: 1.0.0
 */

(function() {
    'use strict';
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initERPModule);
    } else {
        initERPModule();
    }
    
    /**
     * Main initialization
     */
    function initERPModule() {
        // erpTableSearch(); // Disabled - using default Django search
        erpKeyboardShortcuts();
        erpAutosave();
        erpIconifyActions();
        erpConfirmDelete();
        erpEnhanceCheckboxes();
        erpShowShortcutsHint();
    }
    
    /**
     * 1. INSTANT TABLE SEARCH
     * Filters table rows without page reload
     */
    function erpTableSearch() {
        const resultList = document.getElementById('result_list');
        if (!resultList) return;
        
        // Create search wrapper
        const searchWrapper = document.createElement('div');
        searchWrapper.className = 'erp-instant-search';
        searchWrapper.innerHTML = `
            <input type="text" 
                   id="erp-table-search" 
                   placeholder="بحث سريع... (اكتب للتصفية)"
                   autocomplete="off">
            <button type="button" class="search-clear" title="مسح البحث">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Create count indicator
        const searchCount = document.createElement('div');
        searchCount.className = 'erp-search-count';
        searchCount.id = 'erp-search-count';
        
        // Create no results message
        const noResults = document.createElement('div');
        noResults.className = 'erp-no-results';
        noResults.id = 'erp-no-results';
        noResults.innerHTML = `
            <i class="fas fa-search"></i>
            <p>لا توجد نتائج مطابقة</p>
        `;
        
        // Insert before table
        const changelist = document.getElementById('changelist');
        if (changelist) {
            const toolbar = changelist.querySelector('#toolbar');
            if (toolbar) {
                toolbar.parentNode.insertBefore(searchWrapper, toolbar.nextSibling);
            } else {
                changelist.insertBefore(searchWrapper, changelist.firstChild);
            }
            searchWrapper.after(searchCount);
            resultList.after(noResults);
        }
        
        const searchInput = document.getElementById('erp-table-search');
        const clearBtn = searchWrapper.querySelector('.search-clear');
        const rows = resultList.querySelectorAll('tbody tr');
        
        if (!searchInput || rows.length === 0) return;
        
        let debounceTimer;
        
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => filterTable(this.value), 150);
        });
        
        clearBtn.addEventListener('click', function() {
            searchInput.value = '';
            filterTable('');
            searchInput.focus();
        });
        
        function filterTable(query) {
            const searchText = query.toLowerCase().trim();
            let visibleCount = 0;
            
            rows.forEach(row => {
                if (row.classList.contains('empty')) return;
                
                const text = row.textContent.toLowerCase();
                const match = !searchText || text.includes(searchText);
                
                row.classList.toggle('erp-hidden', !match);
                if (match) visibleCount++;
            });
            
            // Update count
            const countEl = document.getElementById('erp-search-count');
            const noResultsEl = document.getElementById('erp-no-results');
            
            if (searchText) {
                countEl.textContent = `عرض ${visibleCount} من ${rows.length} نتيجة`;
                countEl.classList.add('visible');
                noResultsEl.classList.toggle('visible', visibleCount === 0);
            } else {
                countEl.classList.remove('visible');
                noResultsEl.classList.remove('visible');
            }
        }
    }
    
    /**
     * 2. KEYBOARD SHORTCUTS
     * Ctrl+S: Save, Esc: Cancel, Ctrl+N: New, F2: Edit first selected
     */
    function erpKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Skip if user is typing in input/textarea
            const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName);
            
            // Ctrl+S or Cmd+S: Save form
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                const saveBtn = document.querySelector(
                    'input[name="_save"], input[name="_continue"], button[type="submit"]'
                );
                if (saveBtn) {
                    showSaveIndicator('جاري الحفظ...');
                    saveBtn.click();
                }
                return;
            }
            
            // Escape: Cancel / Close modal
            if (e.key === 'Escape') {
                // Close any open modal
                const modal = document.querySelector('.erp-modal-overlay.visible');
                if (modal) {
                    modal.classList.remove('visible');
                    return;
                }
                
                // Otherwise cancel form
                if (!isTyping) {
                    const cancelLink = document.querySelector('.cancel-link, a[href*="changelist"]');
                    if (cancelLink) {
                        cancelLink.click();
                    }
                }
                return;
            }
            
            // Skip other shortcuts if typing
            if (isTyping) return;
            
            // Ctrl+N or Alt+N: New item
            if ((e.ctrlKey || e.altKey) && e.key === 'n') {
                e.preventDefault();
                const addBtn = document.querySelector('.object-tools .addlink, a[href$="/add/"]');
                if (addBtn) {
                    addBtn.click();
                }
                return;
            }
            
            // F2: Edit first selected row
            if (e.key === 'F2') {
                e.preventDefault();
                const selectedRow = document.querySelector('#result_list tbody tr.selected');
                const editLink = selectedRow ? 
                    selectedRow.querySelector('a[href*="/change/"]') :
                    document.querySelector('#result_list tbody tr:first-child a');
                if (editLink) {
                    editLink.click();
                }
                return;
            }
            
            // /: Focus search
            if (e.key === '/') {
                e.preventDefault();
                const searchInput = document.getElementById('erp-table-search') || 
                                   document.getElementById('searchbar');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
                return;
            }
            
            // ?: Show shortcuts panel
            if (e.key === '?' || (e.shiftKey && e.key === '/')) {
                e.preventDefault();
                toggleShortcutsPanel();
                return;
            }
        });
    }
    
    function showSaveIndicator(message) {
        let indicator = document.querySelector('.erp-autosave-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'erp-autosave-indicator';
            document.body.appendChild(indicator);
        }
        
        indicator.innerHTML = `<i class="fas fa-circle-notch fa-spin"></i> ${message}`;
        indicator.classList.add('visible', 'saving');
        indicator.classList.remove('saved');
    }
    
    function toggleShortcutsPanel() {
        let panel = document.querySelector('.erp-shortcuts-panel');
        if (!panel) {
            panel = document.createElement('div');
            panel.className = 'erp-shortcuts-panel';
            panel.innerHTML = `
                <div class="erp-shortcuts-title">
                    <i class="fas fa-keyboard"></i> اختصارات لوحة المفاتيح
                </div>
                <ul class="erp-shortcuts-list">
                    <li>حفظ <kbd>Ctrl</kbd>+<kbd>S</kbd></li>
                    <li>إلغاء <kbd>Esc</kbd></li>
                    <li>جديد <kbd>Ctrl</kbd>+<kbd>N</kbd></li>
                    <li>تعديل <kbd>F2</kbd></li>
                    <li>بحث <kbd>/</kbd></li>
                    <li>إظهار الاختصارات <kbd>?</kbd></li>
                </ul>
            `;
            document.body.appendChild(panel);
        }
        
        panel.classList.toggle('visible');
    }
    
    /**
     * 3. AUTO-SAVE DRAFTS
     * Saves form data to localStorage every 30 seconds
     */
    function erpAutosave() {
        const form = document.querySelector('#content form');
        if (!form || !form.id) return;
        
        const storageKey = `erp_draft_${window.location.pathname}`;
        const AUTOSAVE_INTERVAL = 30000; // 30 seconds
        
        let lastSave = null;
        let hasChanges = false;
        
        // Track changes
        form.addEventListener('input', function() {
            hasChanges = true;
        });
        
        form.addEventListener('change', function() {
            hasChanges = true;
        });
        
        // Load existing draft
        loadDraft();
        
        // Auto-save interval
        setInterval(saveDraft, AUTOSAVE_INTERVAL);
        
        // Save on page unload
        window.addEventListener('beforeunload', function() {
            if (hasChanges) {
                saveDraft();
            }
        });
        
        // Clear draft on successful submit
        form.addEventListener('submit', function() {
            localStorage.removeItem(storageKey);
        });
        
        function getFormData() {
            const data = {};
            const inputs = form.querySelectorAll('input, textarea, select');
            
            inputs.forEach(input => {
                if (!input.name || input.type === 'file' || input.type === 'hidden') return;
                if (input.name.startsWith('csrfmiddleware') || input.name === 'csrfmiddlewaretoken') return;
                
                if (input.type === 'checkbox') {
                    data[input.name] = input.checked;
                } else if (input.type === 'radio') {
                    if (input.checked) data[input.name] = input.value;
                } else {
                    data[input.name] = input.value;
                }
            });
            
            return data;
        }
        
        function saveDraft() {
            if (!hasChanges) return;
            
            const data = {
                timestamp: Date.now(),
                fields: getFormData()
            };
            
            try {
                localStorage.setItem(storageKey, JSON.stringify(data));
                lastSave = Date.now();
                hasChanges = false;
                showAutosaveIndicator('تم حفظ المسودة');
            } catch (e) {
                console.warn('ERP: Could not save draft', e);
            }
        }
        
        function loadDraft() {
            try {
                const saved = localStorage.getItem(storageKey);
                if (!saved) return;
                
                const data = JSON.parse(saved);
                const age = Date.now() - data.timestamp;
                
                // Ignore drafts older than 24 hours
                if (age > 24 * 60 * 60 * 1000) {
                    localStorage.removeItem(storageKey);
                    return;
                }
                
                // Check if form is empty (new record)
                const isNewRecord = window.location.pathname.endsWith('/add/');
                if (!isNewRecord) return; // Only restore for new records
                
                // Show restore prompt
                if (Object.keys(data.fields).length > 0) {
                    showRestorePrompt(data);
                }
            } catch (e) {
                console.warn('ERP: Could not load draft', e);
            }
        }
        
        function showRestorePrompt(data) {
            const timeAgo = formatTimeAgo(data.timestamp);
            
            const prompt = document.createElement('div');
            prompt.className = 'erp-alert erp-alert-info';
            prompt.innerHTML = `
                <i class="fas fa-undo"></i>
                <span>يوجد مسودة محفوظة من ${timeAgo}. 
                    <a href="#" class="erp-restore-draft" style="font-weight:700">استعادة</a> | 
                    <a href="#" class="erp-discard-draft">تجاهل</a>
                </span>
            `;
            
            const content = document.getElementById('content');
            if (content) {
                content.insertBefore(prompt, content.firstChild);
                
                prompt.querySelector('.erp-restore-draft').addEventListener('click', function(e) {
                    e.preventDefault();
                    restoreFields(data.fields);
                    prompt.remove();
                });
                
                prompt.querySelector('.erp-discard-draft').addEventListener('click', function(e) {
                    e.preventDefault();
                    localStorage.removeItem(storageKey);
                    prompt.remove();
                });
            }
        }
        
        function restoreFields(fields) {
            Object.entries(fields).forEach(([name, value]) => {
                const input = form.querySelector(`[name="${name}"]`);
                if (!input) return;
                
                if (input.type === 'checkbox') {
                    input.checked = value;
                } else if (input.type === 'radio') {
                    const radio = form.querySelector(`[name="${name}"][value="${value}"]`);
                    if (radio) radio.checked = true;
                } else {
                    input.value = value;
                }
                
                // Trigger change event
                input.dispatchEvent(new Event('change', { bubbles: true }));
            });
        }
    }
    
    function showAutosaveIndicator(message) {
        let indicator = document.querySelector('.erp-autosave-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'erp-autosave-indicator';
            document.body.appendChild(indicator);
        }
        
        indicator.innerHTML = `<i class="fas fa-check"></i> ${message}`;
        indicator.classList.add('visible', 'saved');
        indicator.classList.remove('saving');
        
        setTimeout(() => {
            indicator.classList.remove('visible');
        }, 2000);
    }
    
    function formatTimeAgo(timestamp) {
        const diff = Date.now() - timestamp;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        
        if (minutes < 1) return 'الآن';
        if (minutes < 60) return `${minutes} دقيقة`;
        if (hours < 24) return `${hours} ساعة`;
        return 'أكثر من يوم';
    }
    
    /**
     * 4. ICONIFY TABLE ACTIONS
     * Converts text action links to icon buttons
     */
    function erpIconifyActions() {
        // Object tools (top action buttons)
        const objectTools = document.querySelector('.object-tools');
        if (objectTools) {
            const addLink = objectTools.querySelector('.addlink');
            if (addLink) {
                addLink.innerHTML = `<i class="fas fa-plus"></i> ${addLink.textContent.trim()}`;
            }
        }
        
        // Result list action links
        const resultList = document.getElementById('result_list');
        if (!resultList) return;
        
        // Add edit icons to first column links
        resultList.querySelectorAll('tbody tr td:first-child a, tbody tr th a').forEach(link => {
            if (!link.querySelector('i')) {
                const icon = document.createElement('i');
                icon.className = 'fas fa-user me-1';
                icon.style.opacity = '0.5';
                link.insertBefore(icon, link.firstChild);
            }
        });
    }
    
    /**
     * 5. CONFIRM DELETE
     * Shows confirmation modal before delete actions
     */
    function erpConfirmDelete() {
        // Create modal overlay
        const modalOverlay = document.createElement('div');
        modalOverlay.className = 'erp-modal-overlay';
        modalOverlay.id = 'erp-confirm-modal';
        modalOverlay.innerHTML = `
            <div class="erp-modal">
                <div class="erp-modal-header">
                    <div class="erp-modal-icon danger">
                        <i class="fas fa-trash-alt"></i>
                    </div>
                    <h3 class="erp-modal-title">تأكيد الحذف</h3>
                </div>
                <div class="erp-modal-body">
                    <p id="erp-modal-message">هل أنت متأكد من حذف هذا العنصر؟</p>
                </div>
                <div class="erp-modal-footer">
                    <button type="button" class="erp-btn erp-btn-secondary" id="erp-modal-cancel">
                        <i class="fas fa-times"></i> إلغاء
                    </button>
                    <button type="button" class="erp-btn erp-btn-danger" id="erp-modal-confirm">
                        <i class="fas fa-trash-alt"></i> حذف
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modalOverlay);
        
        let pendingAction = null;
        
        // Handle delete links
        document.addEventListener('click', function(e) {
            const deleteLink = e.target.closest('.deletelink, a[href*="/delete/"]');
            if (!deleteLink) return;
            
            e.preventDefault();
            pendingAction = () => window.location.href = deleteLink.href;
            
            document.getElementById('erp-modal-message').textContent = 
                'هل أنت متأكد من حذف هذا العنصر؟ هذا الإجراء لا يمكن التراجع عنه.';
            modalOverlay.classList.add('visible');
        });
        
        // Handle batch delete (actions)
        const deleteSelected = document.querySelector('select[name="action"] option[value*="delete"]');
        if (deleteSelected) {
            const actionsForm = document.getElementById('changelist-form');
            if (actionsForm) {
                actionsForm.addEventListener('submit', function(e) {
                    const selectedAction = actionsForm.querySelector('select[name="action"]');
                    if (selectedAction && selectedAction.value.includes('delete')) {
                        const checkedCount = actionsForm.querySelectorAll('input[name="_selected_action"]:checked').length;
                        if (checkedCount > 0) {
                            e.preventDefault();
                            pendingAction = () => actionsForm.submit();
                            
                            document.getElementById('erp-modal-message').textContent = 
                                `هل أنت متأكد من حذف ${checkedCount} عنصر؟ هذا الإجراء لا يمكن التراجع عنه.`;
                            modalOverlay.classList.add('visible');
                        }
                    }
                });
            }
        }
        
        // Modal controls
        document.getElementById('erp-modal-cancel').addEventListener('click', function() {
            modalOverlay.classList.remove('visible');
            pendingAction = null;
        });
        
        document.getElementById('erp-modal-confirm').addEventListener('click', function() {
            modalOverlay.classList.remove('visible');
            if (pendingAction) {
                pendingAction();
                pendingAction = null;
            }
        });
        
        // Close on overlay click
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === modalOverlay) {
                modalOverlay.classList.remove('visible');
                pendingAction = null;
            }
        });
    }
    
    /**
     * 6. ENHANCE CHECKBOXES
     * Add row selection highlighting
     */
    function erpEnhanceCheckboxes() {
        const resultList = document.getElementById('result_list');
        if (!resultList) return;
        
        resultList.addEventListener('change', function(e) {
            if (e.target.type === 'checkbox' && e.target.name === '_selected_action') {
                e.target.closest('tr').classList.toggle('selected', e.target.checked);
            }
        });
        
        // Select all checkbox
        const selectAll = resultList.querySelector('#action-toggle');
        if (selectAll) {
            selectAll.addEventListener('change', function() {
                const checkboxes = resultList.querySelectorAll('input[name="_selected_action"]');
                checkboxes.forEach(cb => {
                    cb.checked = selectAll.checked;
                    cb.closest('tr').classList.toggle('selected', selectAll.checked);
                });
            });
        }
    }
    
    /**
     * 7. SHOW SHORTCUTS HINT
     * Brief tooltip on page load
     */
    function erpShowShortcutsHint() {
        // Only show once per session
        if (sessionStorage.getItem('erp_shortcuts_shown')) return;
        
        const hint = document.createElement('div');
        hint.className = 'erp-autosave-indicator visible';
        hint.style.cssText = 'bottom: 60px;';
        hint.innerHTML = `<i class="fas fa-keyboard"></i> اضغط <kbd style="background:rgba(0,0,0,.1);padding:2px 6px;border-radius:3px">?</kbd> لعرض الاختصارات`;
        document.body.appendChild(hint);
        
        setTimeout(() => {
            hint.classList.remove('visible');
            setTimeout(() => hint.remove(), 300);
        }, 3000);
        
        sessionStorage.setItem('erp_shortcuts_shown', '1');
    }
    
})();
