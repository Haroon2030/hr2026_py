/* ============================================================
   AdminDek JS – HR Pro
   Clean sidebar toggle + Django admin helpers.
   No Jazzmin, no AdminLTE, no grid hacks.
   ============================================================ */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        initSidebarToggle();
        markActiveSidebarLink();
        autoExpandActiveSection();
        initFilterPanel();
        initChangeFormTabs();
    });

    /* ── Sidebar Toggle ────────────────────────────────────── */
    function initSidebarToggle() {
        var btn     = document.getElementById('sidebarToggleBtn');
        var overlay = document.getElementById('sidebarOverlay');
        if (!btn) return;

        btn.addEventListener('click', function () {
            if (window.innerWidth >= 992) {
                // Desktop: toggle pinned (full sidebar) vs icon rail
                document.body.classList.toggle('sidebar-pinned');
                var pinned = document.body.classList.contains('sidebar-pinned');
                try { localStorage.setItem('dk-sidebar-pinned', pinned ? '1' : '0'); } catch (e) {}
            } else {
                // Mobile: toggle open (sidebar slides in from the right)
                document.body.classList.toggle('sidebar-open');
            }
        });

        if (overlay) {
            overlay.addEventListener('click', function () {
                document.body.classList.remove('sidebar-open');
            });
        }

        // Restore desktop pin preference
        try {
            if (window.innerWidth >= 992 && localStorage.getItem('dk-sidebar-pinned') === '1') {
                document.body.classList.add('sidebar-pinned');
            }
        } catch (e) {}

        // Close mobile sidebar on resize to desktop
        window.addEventListener('resize', function () {
            if (window.innerWidth >= 992) {
                document.body.classList.remove('sidebar-open');
            }
        });
    }

    /* ── Mark Active Nav Link ──────────────────────────────── */
    function markActiveSidebarLink() {
        var currentPath = window.location.pathname;
        var sidebarLinks = document.querySelectorAll('.sidebar-nav-link');

        sidebarLinks.forEach(function (link) {
            var href = link.getAttribute('href') || link.dataset.url || '';
            if (!href || href === '#') return;
            // Exact match or path starts with link href (but not for root '/')
            var isRoot = href === '/' || href === '/admin/';
            if (isRoot) {
                if (currentPath === href) link.classList.add('active');
            } else if (currentPath.startsWith(href)) {
                link.classList.add('active');
            }
        });
    }

    /* ── Auto-expand Section Containing Active Link ────────── */
    function autoExpandActiveSection() {
        var activeChild = document.querySelector('.sidebar-nav-child.active');
        if (!activeChild) return;

        var collapsePane = activeChild.closest('.collapse');
        if (!collapsePane) return;

        // Open the collapse pane
        collapsePane.classList.add('show');

        // Update the toggle button aria state
        var header = collapsePane.previousElementSibling;
        if (header && header.classList.contains('nav-section-header')) {
            header.setAttribute('aria-expanded', 'true');
        }
    }

    /* ── Filter Panel: auto-open all details ───────────────── */
    function initFilterPanel() {
        var filter = document.getElementById('changelist-filter');
        if (!filter) return;

        // Open all <details> elements in the filter
        filter.querySelectorAll('details').forEach(function (d) { d.open = true; });
    }

    /* ── Change Form Tabs ──────────────────────────────────── */
    function initChangeFormTabs() {
        var tabBtns = document.querySelectorAll('.admindek-tab-btn');
        if (!tabBtns.length) return;

        // إضافة أيقونات للتبويبات
        var tabIcons = {
            'بيانات الموظف': '👤',
            'البيانات الأساسية': '📋',
            'الراتب والبدلات': '💰',
            'الموقع التنظيمي': '🏢',
            'حالة العامل': '📊',
            'الملفات والمستندات': '📁',
            'المستندات': '📄',
            'الحالة والتكليف': '⚡',
            'سلسلة الاعتمادات الثلاثية': '🔗',
            'معلومات النظام': 'ℹ️',
            'بيانات النظام': '⚙️',
            'الإجازات': '🏖️',
            'الحضور والانصراف': '⏰',
            'المخالفات': '⚠️',
            'الإعدادات': '🔧',
            'التفاصيل': '📝',
            'المرفقات': '📎',
            'الملاحظات': '💬',
            'default': '📌'
        };

        tabBtns.forEach(function (btn) {
            var text = btn.textContent.trim();
            var icon = tabIcons[text] || tabIcons['default'];
            
            // إضافة الأيقونة إذا لم تكن موجودة
            if (!btn.querySelector('.tab-icon')) {
                var iconSpan = document.createElement('span');
                iconSpan.className = 'tab-icon';
                iconSpan.textContent = icon;
                iconSpan.style.marginLeft = '6px';
                iconSpan.style.fontSize = '1rem';
                btn.insertBefore(iconSpan, btn.firstChild);
            }

            btn.addEventListener('click', function () {
                var targetId = this.dataset.tab;

                // Deactivate all buttons and panes
                tabBtns.forEach(function (b) { b.classList.remove('active'); });
                document.querySelectorAll('.admindek-tab-pane').forEach(function (p) {
                    p.classList.remove('active');
                });

                // Activate clicked tab and its pane
                this.classList.add('active');
                var pane = document.getElementById(targetId);
                if (pane) pane.classList.add('active');
            });
        });
    }

})();

