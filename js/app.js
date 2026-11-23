/**
 * BuildTrack - Construction Project Management & Risk Prediction System
 * Core App Coordinator, Router, Utilities, Toast, Confirmation, & Auth Management
 */

(function () {
  'use strict';

  const ROLE_ACCESS = Object.freeze({
    'Admin': {
      landingView: 'dashboard',
      views: ['dashboard', 'projects', 'tasks', 'labour', 'materials', 'finance', 'progress', 'risks', 'reports', 'settings'],
      capabilities: ['*']
    },
    'Site Engineer': {
      landingView: 'projects',
      views: ['projects', 'tasks', 'labour', 'progress', 'reports'],
      capabilities: ['tasks.write', 'labour.attendance', 'progress.write']
    },
    'Storekeeper': {
      landingView: 'materials',
      views: ['materials'],
      capabilities: ['materials.write']
    },
    'Client': {
      landingView: 'projects',
      views: ['projects', 'progress', 'reports'],
      capabilities: []
    }
  });

  const FORM_CAPABILITIES = Object.freeze({
    projectAddEditForm: 'projects.write',
    taskAddEditForm: 'tasks.write',
    workerAddEditForm: 'labour.write',
    materialAddEditForm: 'materials.write',
    materialStockActionForm: 'materials.write',
    expenseAddEditForm: 'finance.write',
    paymentAddEditForm: 'finance.write',
    dailyProgressForm: 'progress.write',
    companySettingsForm: 'settings.write',
    userProfileForm: 'settings.write',
    adminUserForm: 'admin.utilities'
  });

  // Client project records and memberships are already scoped by the Flask API.
  function getClientProjectAssignments() {
    const assignments = Object.create(null);
    const projects = window.DataStore ? window.DataStore.getProjects() : [];
    const clientName = window.BuildTrack?.currentClientIdentity;
    if (clientName) assignments[clientName] = projects.map(project => project.id);
    return assignments;
  }

  function hasRoleCapability(capability) {
    const access = ROLE_ACCESS[window.BuildTrack.currentRole];
    return !!access && (access.capabilities.includes('*') || access.capabilities.includes(capability));
  }

  function actionCapability(element) {
    const inlineAction = `${element.getAttribute('onclick') || ''} ${element.getAttribute('onchange') || ''}`;
    if (/ProjectsController\.(openAddModal|openEditModal|confirmDelete)\(/.test(inlineAction)) return 'projects.write';
    if (/TasksController\./.test(inlineAction)) return 'tasks.write';
    if (/LabourController\.setAttendance|markAllPresent/.test(inlineAction)) return 'labour.attendance';
    if (/LabourController\./.test(inlineAction)) return 'labour.write';
    if (/MaterialsController\.(openAddModal|openEditModal|confirmDelete|openStockActionModal)\(/.test(inlineAction)) return 'materials.write';
    if (/FinanceController\./.test(inlineAction)) return 'finance.write';
    if (/ProgressController\.(openAddModal|confirmDelete)\(/.test(inlineAction)) return 'progress.write';
    if (element.id === 'markAllPresentBtn') return 'labour.attendance';
    const form = element.closest('form');
    return form ? FORM_CAPABILITIES[form.id] || null : null;
  }

  function applyRoleAccess() {
    const role = window.BuildTrack.currentRole;
    const access = ROLE_ACCESS[role];
    if (!access) return;

    document.querySelectorAll('.nav-item-link[data-view]').forEach(link => {
      const restricted = !access.views.includes(link.dataset.view);
      link.classList.toggle('role-access-hidden', restricted);
      link.closest('li')?.classList.toggle('role-access-hidden', restricted);
    });
    document.querySelectorAll('.nav-section-title').forEach(title => {
      const navList = title.nextElementSibling;
      if (navList && navList.classList.contains('sidebar-nav-list')) {
        title.classList.toggle('role-access-hidden', !navList.querySelector('.nav-item-link:not(.role-access-hidden)'));
      }
    });

    const quickCreate = document.querySelector('.quick-action-dropdown-wrap');
    if (quickCreate) quickCreate.classList.toggle('role-access-hidden', !hasRoleCapability('admin.utilities'));
    const adminAccounts = document.getElementById('adminAccountsCard');
    if (adminAccounts) adminAccounts.classList.toggle('role-access-hidden', !hasRoleCapability('admin.utilities'));
    const notifications = document.getElementById('topbarNotifBtn')?.parentElement;
    if (notifications) notifications.classList.toggle('role-access-hidden', !hasRoleCapability('admin.utilities'));
    const globalSearch = document.querySelector('.global-search-bar');
    if (globalSearch) globalSearch.classList.toggle('role-access-hidden', !hasRoleCapability('admin.utilities'));

    document.querySelectorAll('.app-layout [onclick], .app-layout [onchange]').forEach(element => {
      const capability = actionCapability(element);
      if (capability) element.classList.toggle('role-access-hidden', !hasRoleCapability(capability));
    });
    const reportTypeSelect = document.getElementById('reportTypeSelect');
    if (reportTypeSelect) {
      [...reportTypeSelect.options].forEach(option => {
        option.hidden = role === 'Client' ? option.value !== 'progress' :
          role === 'Site Engineer' ? !['progress', 'tasks'].includes(option.value) : false;
      });
      if (role === 'Client' && reportTypeSelect.value !== 'progress') {
        reportTypeSelect.value = 'progress';
        reportTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      } else if (role === 'Site Engineer' && !['progress', 'tasks'].includes(reportTypeSelect.value)) {
        reportTypeSelect.value = 'progress';
        reportTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }
    document.querySelectorAll('.project-finance-column, .project-financials-summary, .project-finance-tab, .project-finance-detail, .project-labour-cost')
      .forEach(element => element.classList.toggle('role-access-hidden', !hasRoleCapability('admin.utilities')));
    const budgetSort = document.querySelector('#projectSortFilter option[value="budget"]');
    if (budgetSort) budgetSort.hidden = !hasRoleCapability('admin.utilities');
    if (!hasRoleCapability('admin.utilities') && document.getElementById('projectSortFilter')?.value === 'budget') {
      document.getElementById('projectSortFilter').value = 'name';
    }
    Object.keys(FORM_CAPABILITIES).forEach(formId => {
      const form = document.getElementById(formId);
      if (!form) return;
      const restricted = !hasRoleCapability(FORM_CAPABILITIES[formId]);
      form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(button => {
        button.classList.toggle('role-access-hidden', restricted);
      });
    });
  }

  function setMobileNavOpen(isOpen) {
    const sidebar = document.getElementById('mainSidebar');
    const menuButton = document.getElementById('mobileMenuBtn');
    if (!sidebar) return;
    sidebar.classList.toggle('mobile-open', isOpen);
    document.body.classList.toggle('mobile-nav-open', isOpen);
    if (menuButton) {
      menuButton.setAttribute('aria-expanded', String(isOpen));
      menuButton.setAttribute('aria-label', isOpen ? 'Close navigation' : 'Open navigation');
    }
  }

  // Master Global BuildTrack Object
  window.BuildTrack = {
    currentView: 'dashboard',
    currentProjectId: 'all',
    currentRole: null,
    currentClientIdentity: null,
    currentAssignedProjectIds: [],
    isClientRole: function () {
      return this.currentRole === 'Client';
    },
    isProjectScopedRole: function () {
      return this.currentRole === 'Client' || this.currentRole === 'Site Engineer';
    },
    canViewFinancials: function () {
      return this.currentRole === 'Admin';
    },
    getClientProjectAssignments: getClientProjectAssignments,
    getClientIdentities: function () {
      return this.currentClientIdentity ? [this.currentClientIdentity] : [];
    },
    getClientProjectIds: function () {
      return this.isProjectScopedRole() ? this.currentAssignedProjectIds : [];
    },
    getVisibleProjects: function () {
      const projects = window.DataStore.getProjects();
      if (!this.isProjectScopedRole()) return projects;
      const assignedIds = new Set(this.getClientProjectIds());
      return projects.filter(project => assignedIds.has(project.id));
    },
    filterClientRecords: function (records, projectFilter = 'all', projectIdField = 'projectId', includeUnassigned = false) {
      if (!this.isProjectScopedRole()) return records;
      const assignedIds = new Set(this.getClientProjectIds());
      if (projectFilter !== 'all' && !assignedIds.has(projectFilter)) return [];
      return records.filter(record => {
        const projectId = record[projectIdField];
        if (includeUnassigned && this.isClientRole() && !projectId) return true;
        return assignedIds.has(projectId) && (projectFilter === 'all' || projectId === projectFilter);
      });
    },
    canAccessProject: function (projectId) {
      return !this.isProjectScopedRole() || this.getClientProjectIds().includes(projectId);
    },
    isSupportedRole: function (role) {
      return Object.prototype.hasOwnProperty.call(ROLE_ACCESS, role);
    },
    
    // Format number to Indian Rupee (₹)
    formatINR: function (val) {
      const num = parseFloat(val);
      if (isNaN(num)) return '₹0';
      
      const isNegative = num < 0;
      const absoluteNum = Math.abs(num);
      
      // Indian numbering grouping format (e.g., 12,50,000)
      const parts = absoluteNum.toFixed(0).split('.');
      let lastThree = parts[0].substring(parts[0].length - 3);
      const otherNumbers = parts[0].substring(0, parts[0].length - 3);
      if (otherNumbers !== '') {
        lastThree = ',' + lastThree;
      }
      const formatted = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree;
      return (isNegative ? '-₹' : '₹') + formatted;
    },

    // Format ISO date (YYYY-MM-DD) to friendly format (e.g. 27 Oct 2026)
    formatDate: function (dateStr) {
      if (!dateStr) return 'N/A';
      try {
        const parts = dateStr.split('-');
        if (parts.length === 3) {
          const date = new Date(parts[0], parts[1] - 1, parts[2]);
          return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
        }
        return dateStr;
      } catch (e) {
        return dateStr;
      }
    },

    // Navigation Switcher
    navigateTo: function (viewId) {
      const access = ROLE_ACCESS[this.currentRole];
      if (access && !access.views.includes(viewId)) {
        this.showToast('This prototype role does not have access to that module.', 'warning');
        viewId = access.landingView;
      }
      const targetView = document.getElementById('view-' + viewId);
      if (!targetView) return;

      // Update active view DOM
      document.querySelectorAll('.view-page').forEach(page => page.classList.remove('active'));
      targetView.classList.add('active');

      // Update sidebar active link
      document.querySelectorAll('.nav-item-link').forEach(link => {
        if (link.getAttribute('data-view') === viewId) {
          link.classList.add('active');
        } else {
          link.classList.remove('active');
        }
      });

      this.currentView = viewId;
      window.location.hash = viewId;
      applyRoleAccess();

      // Close mobile sidebar if open
      const sidebar = document.getElementById('mainSidebar');
      if (sidebar && sidebar.classList.contains('mobile-open')) setMobileNavOpen(false);

      // Scroll to top
      window.scrollTo({ top: 0, behavior: 'smooth' });

      // Trigger view-activated hook
      window.dispatchEvent(new CustomEvent('buildtrack:viewchanged', { detail: { view: viewId } }));
    },

    // Toast Notifications System
    showToast: function (message, type = 'info', duration = 3500) {
      const container = document.getElementById('toastContainer');
      if (!container) return;

      const toast = document.createElement('div');
      toast.className = `toast-message-pill toast-${type}`;
      
      const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-triangle-exclamation',
        info: 'fa-info-circle'
      };

      toast.innerHTML = `
        <div class="toast-icon-wrap"><i class="fa-solid ${icons[type] || 'fa-info-circle'}"></i></div>
        <div class="toast-body-text">${message}</div>
      `;

      container.appendChild(toast);

      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        setTimeout(() => toast.remove(), 300);
      }, duration);
    },

    // Modal Manager
    openModal: function (modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    },

    closeModal: function (modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;
      modal.classList.remove('active');
      document.body.style.overflow = '';
      
      // Reset forms inside modal if any
      const form = modal.querySelector('form');
      if (form) form.reset();
    },

    // Universal Confirmation Dialog
    showConfirm: function (options) {
      const {
        title = 'Are you sure?',
        message = 'This action cannot be undone.',
        confirmText = 'Confirm Delete',
        confirmClass = 'btn-danger',
        onConfirm = () => {}
      } = options;

      const modal = document.getElementById('confirmActionModal');
      if (!modal) return;

      document.getElementById('confirmModalTitle').textContent = title;
      document.getElementById('confirmModalDesc').textContent = message;
      
      const confirmBtn = document.getElementById('confirmModalActionBtn');
      confirmBtn.textContent = confirmText;
      confirmBtn.className = `btn ${confirmClass}`;

      // Clean old event listeners
      const newConfirmBtn = confirmBtn.cloneNode(true);
      confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

      newConfirmBtn.addEventListener('click', () => {
        this.closeModal('confirmActionModal');
        onConfirm();
      });

      this.openModal('confirmActionModal');
    },

    // Refresh Topbar Project Selector
    updateProjectSelector: function () {
      const selector = document.getElementById('globalProjectSelect');
      if (!selector) return;

      const currentVal = selector.value || this.currentProjectId || 'all';
      const projects = this.getVisibleProjects();

      const allLabel = this.isClientRole() ? '📁 All Assigned Projects' : '📁 All Projects (Overview)';
      let html = `<option value="all">${allLabel}</option>`;
      projects.forEach(p => {
        html += `<option value="${p.id}">${p.name}</option>`;
      });

      selector.innerHTML = html;
      selector.value = [...selector.options].some(option => option.value === currentVal) ? currentVal : 'all';

      const projectsBadge = document.getElementById('sidebarProjectsBadge');
      if (projectsBadge) projectsBadge.textContent = projects.length;
    },

    // Refresh Dynamic Notification Center
    updateNotifications: function () {
      const container = document.getElementById('notifItemsList');
      const badge = document.getElementById('topbarNotifBadge');
      if (!container || !badge) return;

      const tasks = window.DataStore.getTasks();
      const materials = window.DataStore.getMaterials();
      const projects = window.DataStore.getProjects();
      const today = new Date().toISOString().split('T')[0];

      const alerts = [];

      // Check overdue tasks
      tasks.forEach(t => {
        if (t.status !== 'completed' && t.dueDate < today) {
          alerts.push({
            id: 'notif-' + t.id,
            type: 'critical',
            icon: 'fa-triangle-exclamation text-rose',
            title: `Overdue Task: ${t.title}`,
            time: `Due on ${this.formatDate(t.dueDate)}`,
            view: 'tasks'
          });
        }
      });

      // Check low stock materials
      materials.forEach(m => {
        if (m.quantity <= m.minStockLevel) {
          alerts.push({
            id: 'notif-' + m.id,
            type: 'warning',
            icon: 'fa-box-open text-amber',
            title: `Low Stock: ${m.name}`,
            time: `Stock: ${m.quantity} ${m.unit} (Min: ${m.minStockLevel})`,
            view: 'materials'
          });
        }
      });

      // Check budget overrun projects
      projects.forEach(p => {
        const util = (p.spent / p.budget) * 100;
        if (util > 90 && p.progress < 75) {
          alerts.push({
            id: 'notif-' + p.id,
            type: 'critical',
            icon: 'fa-chart-pie text-rose',
            title: `Budget Risk: ${p.name}`,
            time: `${util.toFixed(1)}% spent with ${p.progress}% progress`,
            view: 'risks'
          });
        }
      });

      badge.textContent = alerts.length;
      badge.style.display = alerts.length > 0 ? 'flex' : 'none';

      if (alerts.length === 0) {
        container.innerHTML = `
          <div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
            <i class="fa-solid fa-bell-slash" style="font-size: 1.5rem; margin-bottom: 0.5rem; opacity: 0.5;"></i>
            <p>No critical warnings. All systems operational.</p>
          </div>
        `;
        return;
      }

      container.innerHTML = alerts.map(a => `
        <div class="notif-item-row unread" onclick="BuildTrack.navigateTo('${a.view}'); document.getElementById('notifDropdownPanel').classList.remove('show');">
          <div style="font-size: 1.1rem; padding-top: 2px;">
            <i class="fa-solid ${a.icon}"></i>
          </div>
          <div style="flex: 1;">
            <div style="font-size: 0.82rem; font-weight: 600; color: var(--text-main); line-height: 1.3;">${a.title}</div>
            <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">${a.time}</div>
          </div>
        </div>
      `).join('');
    }
  };

  // Initialization & Event Bindings
  document.addEventListener('DOMContentLoaded', function () {
    // 1. Always start at sign-in. LocalStorage can contain a profile from an
    // earlier prototype login, but it is not proof of an active session.
    const authOverlay = document.getElementById('authOverlay');
    const appLayout = document.querySelector('.app-layout');
    authOverlay.classList.remove('hidden');
    if (appLayout) appLayout.classList.add('auth-locked');

    // Reapply role visibility as existing controllers replace dynamic lists.
    if (appLayout && window.MutationObserver) {
      const roleObserver = new MutationObserver(applyRoleAccess);
      roleObserver.observe(appLayout, { childList: true, subtree: true });
    }

    document.addEventListener('click', function (event) {
      const action = event.target.closest('[onclick], #markAllPresentBtn');
      const capability = action && actionCapability(action);
      if (capability && !hasRoleCapability(capability)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        window.BuildTrack.showToast('This action is unavailable for the selected prototype role.', 'warning');
      }
    }, true);

    document.addEventListener('change', function (event) {
      const action = event.target.closest('[onchange]');
      const capability = action && actionCapability(action);
      if (capability && !hasRoleCapability(capability)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        window.BuildTrack.showToast('This action is unavailable for the selected prototype role.', 'warning');
      }
    }, true);

    document.addEventListener('submit', function (event) {
      const capability = FORM_CAPABILITIES[event.target.id];
      if (capability && !hasRoleCapability(capability)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        window.BuildTrack.showToast('This action is unavailable for the selected prototype role.', 'warning');
      }
    }, true);

    // 2. Initialize Topbar Selectors
    window.BuildTrack.updateProjectSelector();
    window.BuildTrack.updateNotifications();

    // 3. Setup Hash Route
    const initialHash = window.location.hash.replace('#', '') || 'dashboard';
    window.BuildTrack.navigateTo(initialHash);

    // 4. Global Navigation Clicks
    document.querySelectorAll('.nav-item-link').forEach(link => {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        const view = this.getAttribute('data-view');
        if (view) window.BuildTrack.navigateTo(view);
      });
    });

    // 5. Sidebar Toggle (Desktop Collapse & Mobile Open)
    const sidebar = document.getElementById('mainSidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    if (toggleBtn && sidebar) {
      toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
      });
    }

    if (mobileMenuBtn && sidebar) {
      mobileMenuBtn.addEventListener('click', () => {
        setMobileNavOpen(!sidebar.classList.contains('mobile-open'));
      });
    }
    if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', () => setMobileNavOpen(false));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && sidebar?.classList.contains('mobile-open')) setMobileNavOpen(false);
    });
    sidebar?.querySelector('.brand-link')?.addEventListener('click', () => setMobileNavOpen(false));

    // 6. Global Project Filter Change
    const projectSelect = document.getElementById('globalProjectSelect');
    if (projectSelect) {
      projectSelect.addEventListener('change', function () {
        window.BuildTrack.currentProjectId = this.value;
        window.dispatchEvent(new CustomEvent('buildtrack:projectfilterchanged', {
          detail: { projectId: this.value }
        }));
        window.BuildTrack.showToast(`Active project filter set to: ${this.options[this.selectedIndex].text}`, 'info', 2000);
      });
    }

    // 7. Quick Create Action Dropdown
    const quickCreateBtn = document.getElementById('quickCreateBtn');
    const quickMenu = document.getElementById('quickCreateDropdownMenu');
    if (quickCreateBtn && quickMenu) {
      quickCreateBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        quickMenu.classList.toggle('show');
      });
    }

    // 8. Notification Bell Dropdown
    const notifBtn = document.getElementById('topbarNotifBtn');
    const notifPanel = document.getElementById('notifDropdownPanel');
    if (notifBtn && notifPanel) {
      notifBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        notifPanel.classList.toggle('show');
      });
    }

    // Close open dropdowns on document click
    document.addEventListener('click', () => {
      if (quickMenu) quickMenu.classList.remove('show');
      if (notifPanel) notifPanel.classList.remove('show');
    });

    // 9. Global Modal Backdrop & Close Handlers
    document.querySelectorAll('.modal-overlay').forEach(modal => {
      modal.addEventListener('click', function (e) {
        if (e.target === this) {
          window.BuildTrack.closeModal(this.id);
        }
      });

      const closeBtns = modal.querySelectorAll('.modal-close-x, [data-close-modal]');
      closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          window.BuildTrack.closeModal(modal.id);
        });
      });
    });

    // 10. Listen to Data Changes to refresh common components
    window.addEventListener('buildtrack:datachanged', function () {
      window.BuildTrack.updateProjectSelector();
      window.BuildTrack.updateNotifications();
    });

    // 11. Auth Form Handling
    setupAuthListeners();
    window.addEventListener('buildtrack:sessionexpired', () => {
      window.DataStore.logout();
      window.BuildTrack.currentRole = null;
      window.BuildTrack.currentClientIdentity = null;
      window.BuildTrack.currentAssignedProjectIds = [];
      document.querySelector('.app-layout')?.classList.add('auth-locked');
      authOverlay.classList.remove('hidden');
      window.BuildTrack.showToast('Your session expired. Sign in again to continue.', 'warning', 6000);
    });

    // Restore only the remembered email address; never persist the password.
    const rememberedEmail = localStorage.getItem('buildtrack_remembered_email');
    const emailInput = document.getElementById('loginEmail');
    const rememberMe = document.getElementById('rememberMe');
    if (rememberedEmail && emailInput && rememberMe) {
      emailInput.value = rememberedEmail;
      rememberMe.checked = true;
    }

    // Restore an already authenticated Flask session after refresh.
    window.ApiService.auth.me().then(async response => {
      const user = response?.user;
      if (!user) return;
      window.BuildTrack.currentRole = user.role;
      window.BuildTrack.currentClientIdentity = user.role === 'Client' ? user.name : null;
      window.BuildTrack.currentAssignedProjectIds = user.assignedProjectIds || [];
      await window.DataStore.hydrateFromApi();
      window.DataStore.saveUser(user);
      applyRoleAccess();
      window.BuildTrack.updateProjectSelector();
      authOverlay.classList.add('hidden');
      document.querySelector('.app-layout')?.classList.remove('auth-locked');
      updateUserProfileUI(user);
      window.BuildTrack.navigateTo(ROLE_ACCESS[user.role]?.landingView || 'dashboard');
    }).catch(error => {
      if (error.status === 401 && window.DataStore.getUser()?.email) {
        window.BuildTrack.showToast('Your session expired. Sign in again to continue.', 'info', 5000);
      } else if (error.status !== 401) {
        window.BuildTrack.showToast(`Could not connect to the BuildTrack server: ${error.message}`, 'warning', 7000);
      }
    });
  });

  // UI User Profile updater
  function updateUserProfileUI(user) {
    if (!user) return;
    const nameEls = document.querySelectorAll('.user-display-name, .topbar-user-name');
    const roleEls = document.querySelectorAll('.user-role-badge');
    const avatarEls = document.querySelectorAll('.user-avatar-circle, .topbar-avatar');

    nameEls.forEach(el => el.textContent = user.name);
    roleEls.forEach(el => el.textContent = user.role);
    
    // Initials
    const initials = user.name ? user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'BT';
    avatarEls.forEach(el => el.textContent = initials);
  }

  // Setup Authentication Listeners
  function setupAuthListeners() {
    const loginForm = document.getElementById('loginForm');
    const authOverlay = document.getElementById('authOverlay');
    const roleSelector = document.getElementById('loginRole');
    const clientIdentityGroup = document.getElementById('clientIdentityGroup');
    if (clientIdentityGroup) clientIdentityGroup.hidden = true;

    // Show/Hide Password
    document.querySelectorAll('.password-toggle-eye').forEach(eye => {
      eye.addEventListener('click', function () {
        const input = this.previousElementSibling;
        const icon = this.querySelector('i');
        if (input && input.type === 'password') {
          input.type = 'text';
          this.setAttribute('aria-label', 'Hide password');
          this.setAttribute('aria-pressed', 'true');
          if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
        } else if (input) {
          input.type = 'password';
          this.setAttribute('aria-label', 'Show password');
          this.setAttribute('aria-pressed', 'false');
          if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
        }
      });
    });

    // Login Form Submit
    if (loginForm) {
      loginForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const email = document.getElementById('loginEmail').value.trim();
        const pass = document.getElementById('loginPassword').value;
        const selectedRole = document.getElementById('loginRole').value;
        const rememberEmail = document.getElementById('rememberMe').checked;

        const submitBtn = loginForm.querySelector('button[type="submit"]');
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Signing in…'; }

        let authenticated = false;
        try {
          let apiUser = null;
          const result = await window.ApiService.auth.login(email, pass);
          apiUser = result?.user;
          if (!apiUser) throw new Error('The server did not return an authenticated account.');
          authenticated = true;
          const role = apiUser.role;
          if (selectedRole !== role) {
            window.BuildTrack.showToast(`Signed in with your assigned role: ${role}.`, 'info');
          }
          document.getElementById('loginRole').value = role;
          window.BuildTrack.currentRole = role;
          window.BuildTrack.currentClientIdentity = role === 'Client' ? apiUser.name : null;
          window.BuildTrack.currentAssignedProjectIds = apiUser.assignedProjectIds || [];
          await window.DataStore.hydrateFromApi();
          window.DataStore.saveUser(apiUser);

          if (rememberEmail) localStorage.setItem('buildtrack_remembered_email', email);
          else localStorage.removeItem('buildtrack_remembered_email');
          window.BuildTrack.currentProjectId = 'all';
          applyRoleAccess();
          loadAdminAccounts();
          window.BuildTrack.updateProjectSelector();
          window.dispatchEvent(new CustomEvent('buildtrack:clientchanged', {
            detail: { clientName: window.BuildTrack.currentClientIdentity }
          }));
          authOverlay.classList.add('hidden');
          document.querySelector('.app-layout')?.classList.remove('auth-locked');
          updateUserProfileUI(apiUser);
          window.BuildTrack.showToast(`Welcome back, ${apiUser.name || email}!`, 'success');
          window.BuildTrack.navigateTo(ROLE_ACCESS[role]?.landingView || 'dashboard');
        } catch (error) {
          const message = authenticated
            ? `Your credentials were accepted, but BuildTrack could not load project data: ${error.message}`
            : (error.status === 401 ? 'Invalid email or password. Check your email and password, or ask an Admin to confirm your account is active.' : `Could not sign in: ${error.message || 'BuildTrack server unavailable.'}`);
          window.BuildTrack.showToast(message, 'error', 7000);
        } finally {
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Sign In'; }
        }
      });
    }

    // Logout Action
    document.querySelectorAll('.user-logout-quick-btn, #logoutActionBtn').forEach(btn => {
      btn.addEventListener('click', () => {
        window.BuildTrack.showConfirm({
          title: 'Sign Out of BuildTrack?',
          message: 'Are you sure you want to log out of the construction management portal?',
          confirmText: 'Log Out',
          confirmClass: 'btn-outline',
          onConfirm: async () => {
            // Keep the local session UI intact if Flask cannot confirm logout.
            if (window.ApiService) {
              try {
                await window.ApiService.auth.logout();
              } catch (error) {
                if (error.status !== 401) {
                  window.BuildTrack.showToast(`Could not sign out from the BuildTrack server: ${error.message}`, 'error', 7000);
                  return;
                }
              }
            }
            window.DataStore.logout();
            window.BuildTrack.currentRole = null;
            window.BuildTrack.currentClientIdentity = null;
            window.BuildTrack.currentAssignedProjectIds = [];
            window.BuildTrack.currentProjectId = 'all';
            window.BuildTrack.updateProjectSelector();
            document.querySelector('.app-layout')?.classList.add('auth-locked');
            document.getElementById('loginPassword').value = '';
            authOverlay.classList.remove('hidden');
            window.BuildTrack.showToast('You have been logged out safely.', 'info');
          }
        });
      });
    });

    // Administrator account management (server-side role checks remain authoritative).
    const accountsCard = document.getElementById('adminAccountsCard');
    const accountForm = document.getElementById('adminUserForm');
    const accountsBody = document.getElementById('adminUsersBody');
    const projectSelectForAccounts = document.getElementById('adminUserProjects');
    const userById = new Map();
    const accountButton = document.getElementById('newUserAccountBtn');
    const cancelAccountButton = document.getElementById('cancelAdminUserBtn');
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    async function loadAdminAccounts() {
      if (!accountsCard || window.BuildTrack.currentRole !== 'Admin') return;
      accountsCard.classList.remove('role-access-hidden');
      try {
        const [userResult, projectResult] = await Promise.all([window.ApiService.auth.users(), window.ApiService.projects.list()]);
        userById.clear();
        (userResult.users || []).forEach(user => userById.set(String(user.id), user));
        const projects = projectResult.projects || [];
        projectSelectForAccounts.innerHTML = projects.map(project => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.name)}</option>`).join('');
        const projectNames = new Map(projects.map(project => [String(project.id), project.name]));
        accountsBody.innerHTML = [...userById.values()].map(user => `<tr><td>${escapeHtml(user.name)}</td><td>${escapeHtml(user.email)}</td><td>${escapeHtml(user.role)}</td><td>${user.isActive ? 'Active' : 'Inactive'}</td><td>${(user.assignedProjectIds || []).map(id => escapeHtml(projectNames.get(String(id)) || id)).join(', ') || '—'}</td><td><button type="button" class="btn btn-outline btn-sm" data-edit-user="${escapeHtml(user.id)}">Edit</button></td></tr>`).join('') || '<tr><td colspan="6">No registered accounts.</td></tr>';
      } catch (error) {
        accountsBody.innerHTML = `<tr><td colspan="6">${escapeHtml(error.message || 'Could not load accounts.')}</td></tr>`;
      }
    }
    function resetAccountForm() {
      accountForm.reset();
      document.getElementById('adminUserId').value = '';
      document.getElementById('adminUserIsActive').checked = true;
      document.getElementById('adminUserPassword').required = true;
      document.getElementById('adminUserPasswordHelp').textContent = 'At least 8 characters.';
      document.getElementById('saveAdminUserBtn').textContent = 'Create account';
      accountForm.hidden = true;
    }
    accountButton?.addEventListener('click', () => { resetAccountForm(); accountForm.hidden = false; });
    cancelAccountButton?.addEventListener('click', resetAccountForm);
    accountsBody?.addEventListener('click', event => {
      const button = event.target.closest('[data-edit-user]');
      if (!button) return;
      const user = userById.get(button.dataset.editUser);
      if (!user) return;
      document.getElementById('adminUserId').value = user.id;
      document.getElementById('adminUserName').value = user.name;
      document.getElementById('adminUserEmail').value = user.email;
      document.getElementById('adminUserRole').value = user.role;
      document.getElementById('adminUserIsActive').checked = !!user.isActive;
      document.getElementById('adminUserPassword').value = '';
      document.getElementById('adminUserPassword').required = false;
      document.getElementById('adminUserPasswordHelp').textContent = 'Leave blank to keep the current password; enter at least 8 characters to reset it.';
      [...projectSelectForAccounts.options].forEach(option => { option.selected = (user.assignedProjectIds || []).map(String).includes(option.value); });
      document.getElementById('saveAdminUserBtn').textContent = 'Save changes';
      accountForm.hidden = false;
      accountForm.scrollIntoView({behavior:'smooth', block:'center'});
    });
    accountForm?.addEventListener('submit', async event => {
      event.preventDefault();
      const id = document.getElementById('adminUserId').value;
      const role = document.getElementById('adminUserRole').value;
      const payload = {name:document.getElementById('adminUserName').value.trim(), email:document.getElementById('adminUserEmail').value.trim(), role, isActive:document.getElementById('adminUserIsActive').checked, assignedProjectIds:['Client','Site Engineer'].includes(role) ? [...projectSelectForAccounts.selectedOptions].map(option => option.value) : []};
      const password = document.getElementById('adminUserPassword').value;
      if (password) payload.password = password;
      try {
        if (id) await window.ApiService.auth.updateUser(id, payload);
        else await window.ApiService.auth.register(payload);
        resetAccountForm();
        await loadAdminAccounts();
        window.BuildTrack.showToast(id ? 'Account updated.' : 'Account created.', 'success');
      } catch (error) { window.BuildTrack.showToast(error.message || 'Could not save account.', 'error'); }
    });
    loadAdminAccounts();
  }

})();
