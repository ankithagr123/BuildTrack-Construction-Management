/**
 * BuildTrack - Construction Project Management & Risk Prediction System
 * Settings Controller: Contractor Profile, INR Currency Preferences, Notifications & Data Reset
 */

(function () {
  'use strict';

  function initSettings() {
    loadSettingsData();
    setupEventHandlers();
  }

  function loadSettingsData() {
    const settings = window.DataStore.getSettings();
    const user = window.DataStore.getUser();

    // Populate Company Profile
    setVal('settingsCompanyName', settings.companyName);
    setVal('settingsContractorName', settings.contractorName);
    setVal('settingsEmail', settings.email);
    setVal('settingsPhone', settings.phone);
    setVal('settingsGstin', settings.gstin);
    setVal('settingsLicense', settings.licenseNumber);

    // Populate User Profile
    setVal('profileUserName', user.name);
    setVal('profileUserEmail', user.email);
    setVal('profileUserRole', user.role);

    // Populate Preferences
    const themeSelect = document.getElementById('settingsThemeSelect');
    if (themeSelect) themeSelect.value = settings.theme || 'light';

    const notifThreshold = document.getElementById('settingsBudgetThreshold');
    if (notifThreshold) notifThreshold.value = settings.notifications?.budgetThreshold || 85;
  }

  function setVal(id, val) {
    const el = document.getElementById(id);
    if (el && val !== undefined) el.value = val;
  }

  async function refreshDemoDataState() {
    const loadButton = document.getElementById('loadDemoDataBtn');
    const removeButton = document.getElementById('removeDemoDataBtn');
    if (!loadButton || window.BuildTrack.currentRole !== 'Admin') return;
    try {
      const state = await window.ApiService.demoData.status();
      loadButton.hidden = !!state.loaded;
      if (removeButton) removeButton.hidden = !state.loaded;
    } catch (error) {
      window.BuildTrack.showToast(`Could not check demo data status: ${error.message}`, 'warning');
    }
  }

  function setupEventHandlers() {
    const companyForm = document.getElementById('companySettingsForm');
    const profileForm = document.getElementById('userProfileForm');
    const importDataBtn = document.getElementById('importBrowserDataBtn');
    const themeSelect = document.getElementById('settingsThemeSelect');
    const loadDemoDataBtn = document.getElementById('loadDemoDataBtn');
    const removeDemoDataBtn = document.getElementById('removeDemoDataBtn');

    if (companyForm) {
      companyForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const settings = window.DataStore.getSettings();
        settings.companyName = document.getElementById('settingsCompanyName').value.trim();
        settings.contractorName = document.getElementById('settingsContractorName').value.trim();
        settings.email = document.getElementById('settingsEmail').value.trim();
        settings.phone = document.getElementById('settingsPhone').value.trim();
        settings.gstin = document.getElementById('settingsGstin').value.trim();
        settings.licenseNumber = document.getElementById('settingsLicense').value.trim();
        settings.notifications.budgetThreshold = parseInt(document.getElementById('settingsBudgetThreshold').value, 10) || 85;

        window.DataStore.saveSettings(settings);
        window.BuildTrack.showToast('Contractor firm profile updated successfully!', 'success');
      });
    }

    if (profileForm) {
      profileForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const user = window.DataStore.getUser();
        user.name = document.getElementById('profileUserName').value.trim();
        user.email = document.getElementById('profileUserEmail').value.trim();
        user.role = document.getElementById('profileUserRole').value.trim();

        window.DataStore.saveUser(user);
        
        // Update UI names
        document.querySelectorAll('.user-display-name, .topbar-user-name').forEach(el => el.textContent = user.name);
        document.querySelectorAll('.user-role-badge').forEach(el => el.textContent = user.role);

        window.BuildTrack.showToast('User credentials & title updated!', 'success');
      });
    }

    if (themeSelect) {
      themeSelect.addEventListener('change', function () {
        if (this.value === 'dark') {
          document.body.classList.add('theme-dark');
        } else {
          document.body.classList.remove('theme-dark');
        }
        window.BuildTrack.showToast(`Theme switched to ${this.value} mode.`, 'info');
      });
    }

    if (importDataBtn) {
      importDataBtn.addEventListener('click', () => {
        window.BuildTrack.showConfirm({
          title: 'Import the Saved Browser Backup?',
          message: 'Existing SQLite records with matching IDs will be kept. New records will be added to SQLite.',
          confirmText: 'Import Backup',
          confirmClass: 'btn-primary',
          onConfirm: async () => {
            try {
              const result = await window.DataStore.importLegacyBackup();
              window.BuildTrack.showToast(`Imported ${result.imported} records; skipped ${result.skipped} duplicates.`, 'success');
            } catch (error) {
              window.BuildTrack.showToast(`Import failed: ${error.message}`, 'error');
            }
          }
        });
      });
    }

    if (loadDemoDataBtn) {
      loadDemoDataBtn.addEventListener('click', () => {
        if (!window.BuildTrack?.showConfirm) {
          window.BuildTrack?.showToast?.('The confirmation dialog is unavailable. Reload BuildTrack and try again.', 'error', 7000);
          return;
        }
        window.BuildTrack.showConfirm({
          title: 'Load Construction Demo Data?',
          message: 'This will add four sample construction projects plus workers, attendance, inventory and stock history, expenses, payments, tasks, and daily progress reports to the existing SQLite database. Existing accounts and records will be preserved. The sample dataset can only be loaded once.',
          confirmText: 'Add Demo Records',
          confirmClass: 'btn-primary',
          onConfirm: async () => {
            const originalLabel = loadDemoDataBtn.innerHTML;
            loadDemoDataBtn.disabled = true;
            loadDemoDataBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Loading demo data…';
            window.BuildTrack.showToast('Saving the sample construction records to SQLite…', 'info', 5000);
            try {
              const result = await window.ApiService.demoData.load();
              const counts = result.counts || {};
              const countOrder = [
                ['projects', 'projects'], ['workers', 'workers'], ['attendance', 'attendance entries'],
                ['tasks', 'tasks'], ['materials', 'materials'], ['stockTransactions', 'stock transactions'],
                ['expenses', 'expenses'], ['payments', 'payments'], ['progressReports', 'progress reports']
              ];
              const total = countOrder.reduce((sum, [key]) => sum + Number(counts[key] || 0), 0);
              const summary = countOrder.filter(([key]) => Number(counts[key] || 0) > 0)
                .map(([key, label]) => `${counts[key]} ${label}`).join(', ');
              window.BuildTrack.showToast(`Demo data saved: ${total} records created (${summary}).`, 'success', 9000);
              try {
                await window.DataStore.hydrateFromApi();
              } catch (refreshError) {
                window.BuildTrack.showToast(`Demo records were saved, but the screen could not refresh: ${refreshError.message}`, 'warning', 9000);
              }
              await refreshDemoDataState();
            } catch (error) {
              window.BuildTrack.showToast(error.message || 'Demo data could not be loaded.', 'error', 7000);
            } finally {
              loadDemoDataBtn.disabled = false;
              loadDemoDataBtn.innerHTML = originalLabel;
            }
          }
        });
      });
    }
    if (removeDemoDataBtn) {
      removeDemoDataBtn.addEventListener('click', () => {
        window.BuildTrack.showConfirm({
          title: 'Remove Generated Demo Data?',
          message: 'This removes only records recorded in BuildTrack’s demo ownership list. If additional tasks, attendance or stock history have since been added to the demo projects, removal will stop without deleting anything.',
          confirmText: 'Remove Demo Records',
          confirmClass: 'btn-outline',
          onConfirm: async () => {
            removeDemoDataBtn.disabled = true;
            try {
              const result = await window.ApiService.demoData.remove();
              await window.DataStore.hydrateFromApi();
              await refreshDemoDataState();
              window.BuildTrack.showToast(`${result.removed?.removedRecords || 0} generated demo records removed.`, 'success', 7000);
            } catch (error) {
              window.BuildTrack.showToast(error.message || 'Demo records could not be removed.', 'error', 7000);
            } finally {
              removeDemoDataBtn.disabled = false;
            }
          }
        });
      });
    }
    refreshDemoDataState();
  }

  document.addEventListener('DOMContentLoaded', () => {
    window.addEventListener('buildtrack:viewchanged', (e) => {
      if (e.detail.view === 'settings') {
        loadSettingsData();
        refreshDemoDataState();
      }
    });

    initSettings();
  });

  window.SettingsController = {
    load: loadSettingsData,
    refreshDemoDataState
  };
})();
