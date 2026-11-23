/** BuildTrack PWA install prompt, service worker registration, and connectivity notice. */
(function () {
  'use strict';

  let installPrompt = null;
  const installButton = document.getElementById('installAppBtn');
  const iosInstallHelp = document.getElementById('iosInstallHelp');
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isInstalled = () => window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true;

  function setInstallButton(visible, label) {
    if (!installButton) return;
    installButton.hidden = !visible;
    if (label) installButton.querySelector('span')?.replaceChildren(document.createTextNode(label));
  }

  function showConnectionState() {
    if (!window.BuildTrack) return;
    if (!navigator.onLine) {
      window.BuildTrack.showToast('You are offline. Changes cannot sync to SQLite until the server connection returns.', 'warning', 5000);
    } else if (showConnectionState.wasOffline) {
      window.BuildTrack.showToast('Connection restored.', 'success', 2500);
    }
    showConnectionState.wasOffline = !navigator.onLine;
  }

  window.addEventListener('beforeinstallprompt', event => {
    if (isInstalled()) return;
    event.preventDefault();
    installPrompt = event;
    setInstallButton(true, 'Install app');
  });

  window.addEventListener('appinstalled', () => {
    installPrompt = null;
    setInstallButton(false);
    window.BuildTrack?.showToast('BuildTrack is installed and ready for your next site visit.', 'success');
  });

  if (installButton) {
    installButton.addEventListener('click', async () => {
      if (!installPrompt) {
        if (isIOS) window.BuildTrack?.showToast?.('To install BuildTrack, tap Share, then choose “Add to Home Screen”.', 'info', 6000);
        return;
      }
      const promptEvent = installPrompt;
      installPrompt = null;
      await promptEvent.prompt();
      const choice = await promptEvent.userChoice;
      if (choice?.outcome === 'accepted') setInstallButton(false);
      else setInstallButton(true, 'Install app');
    });
  }

  if (isIOS && !isInstalled()) {
    setInstallButton(true, 'Add to Home Screen');
    if (iosInstallHelp) iosInstallHelp.hidden = false;
  }
  if (isInstalled()) setInstallButton(false);

  window.addEventListener('offline', showConnectionState);
  window.addEventListener('online', showConnectionState);
  showConnectionState.wasOffline = !navigator.onLine;
  if (!navigator.onLine) showConnectionState();

  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('./service-worker.js', { updateViaCache: 'none' })
        .then(registration => registration.update().catch(() => {}))
        .catch(error => {
          console.warn('BuildTrack offline support could not start:', error);
          window.BuildTrack?.showToast?.('Offline support could not be enabled in this browser.', 'warning', 5000);
        });
    });
  }
})();
