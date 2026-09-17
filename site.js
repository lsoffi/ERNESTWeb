(() => {
  const CONSENT_KEY = "ernest-cookie-consent";
  const THEME_KEY = "ernest-theme";
  const root = document.documentElement;

  const getSystemTheme = () =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

  const getPolicyHref = () => "cookie-policy-eu.html";

  const readConsent = () => {
    try {
      const raw = localStorage.getItem(CONSENT_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  };

  const canStorePreferences = () => readConsent()?.preferences === true;

  const readStoredTheme = () => {
    if (!canStorePreferences()) return null;
    try {
      return localStorage.getItem(THEME_KEY);
    } catch {
      return null;
    }
  };

  const updateThemeAssets = (theme) => {
    const brandLogo = document.querySelector(".brand-logo img");
    if (!brandLogo) return;
    const nextSrc = theme === "dark" ? brandLogo.dataset.darkSrc : brandLogo.dataset.lightSrc;
    if (nextSrc) brandLogo.src = nextSrc;
  };

  const applyTheme = (theme, { persist = false } = {}) => {
    root.setAttribute("data-theme", theme);
    document.querySelectorAll(".theme-toggle").forEach((toggle) => {
      toggle.setAttribute("aria-pressed", String(theme === "dark"));
    });
    updateThemeAssets(theme);

    if (!persist) return;

    try {
      if (canStorePreferences()) {
        localStorage.setItem(THEME_KEY, theme);
      } else {
        localStorage.removeItem(THEME_KEY);
      }
    } catch {
      // Ignore storage errors and keep the in-memory theme.
    }
  };

  const syncThemeWithConsent = () => {
    const storedTheme = readStoredTheme();
    const nextTheme = storedTheme || getSystemTheme();
    applyTheme(nextTheme);
  };

  const writeConsent = (preferencesEnabled) => {
    const payload = {
      necessary: true,
      preferences: Boolean(preferencesEnabled),
      analytics: false,
      updatedAt: new Date().toISOString(),
    };

    try {
      localStorage.setItem(CONSENT_KEY, JSON.stringify(payload));
      if (!payload.preferences) {
        localStorage.removeItem(THEME_KEY);
      }
    } catch {
      // Ignore storage errors and continue with the current runtime state.
    }

    closeConsentPanel();
    hideConsentBanner();
    syncThemeWithConsent();
  };

  const buildConsentMarkup = () => {
    if (document.querySelector(".cookie-banner")) return;

    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <div class="cookie-banner" hidden>
        <div class="cookie-banner-copy">
          <p class="cookie-banner-title">Manage Consent</p>
          <p class="cookie-banner-text">
            To provide the best experience, we use technologies like cookies to store and/or access device information.
            Consenting to these technologies will allow us to process data such as browsing behavior or unique IDs on this site.
            Not consenting or withdrawing consent, may adversely affect certain features and functions.
            <a href="${getPolicyHref()}">Cookie Policy</a>
          </p>
        </div>
        <div class="cookie-banner-actions">
          <button class="cookie-btn cookie-btn-secondary" type="button" data-consent-action="deny">
            Deny
          </button>
          <button class="cookie-btn cookie-btn-secondary" type="button" data-consent-action="preferences">
            Preferences
          </button>
          <button class="cookie-btn cookie-btn-primary" type="button" data-consent-action="accept">
            Accept
          </button>
        </div>
      </div>

      <div class="cookie-panel-backdrop" hidden></div>
      <section class="cookie-panel" aria-labelledby="cookie-panel-title" hidden>
        <div class="cookie-panel-header">
          <h2 id="cookie-panel-title">Cookie Preferences</h2>
          <button class="cookie-panel-close" type="button" aria-label="Close preferences">
            Close
          </button>
        </div>
        <p class="cookie-panel-text">
          ERNEST does not use profiling or marketing cookies. You can enable optional
          preference storage to remember your color theme between visits.
        </p>
        <div class="cookie-option">
          <div>
            <h3>Necessary storage</h3>
            <p>Always active. Stores your consent choice and basic site functionality.</p>
          </div>
          <span class="cookie-option-lock">Always on</span>
        </div>
        <label class="cookie-option cookie-option-toggle">
          <div>
            <h3>Preference storage</h3>
            <p>Remembers your light or dark theme selection for future visits.</p>
          </div>
          <input type="checkbox" id="cookie-preferences-toggle" />
          <span class="cookie-switch" aria-hidden="true"></span>
        </label>
        <div class="cookie-panel-footer">
          <a class="cookie-policy-link" href="${getPolicyHref()}">Open cookie policy</a>
          <button class="cookie-btn cookie-btn-primary" type="button" data-consent-action="save-preferences">
            Save preferences
          </button>
        </div>
      </section>
    `;

    document.body.append(...wrapper.children);
  };

  const getConsentElements = () => ({
    banner: document.querySelector(".cookie-banner"),
    backdrop: document.querySelector(".cookie-panel-backdrop"),
    panel: document.querySelector(".cookie-panel"),
    preferencesToggle: document.querySelector("#cookie-preferences-toggle"),
  });

  const showConsentBanner = () => {
    const { banner } = getConsentElements();
    if (banner) banner.hidden = false;
  };

  const hideConsentBanner = () => {
    const { banner } = getConsentElements();
    if (banner) banner.hidden = true;
  };

  const openConsentPanel = () => {
    const { backdrop, panel, preferencesToggle } = getConsentElements();
    const consent = readConsent();
    if (preferencesToggle) preferencesToggle.checked = consent?.preferences === true;
    if (backdrop) backdrop.hidden = false;
    if (panel) panel.hidden = false;
  };

  function closeConsentPanel() {
    const { backdrop, panel } = getConsentElements();
    if (backdrop) backdrop.hidden = true;
    if (panel) panel.hidden = true;
  }

  const bindConsentEvents = () => {
    document.addEventListener("click", (event) => {
      const target = event.target.closest("[data-consent-action], .cookie-panel-close, .cookie-panel-backdrop");
      if (!target) return;

      if (target.matches(".cookie-panel-close, .cookie-panel-backdrop")) {
        closeConsentPanel();
        return;
      }

      const action = target.getAttribute("data-consent-action");
      if (action === "accept") {
        writeConsent(true);
      } else if (action === "deny") {
        writeConsent(false);
      } else if (action === "preferences") {
        openConsentPanel();
      } else if (action === "save-preferences") {
        const { preferencesToggle } = getConsentElements();
        writeConsent(preferencesToggle?.checked === true);
      }
    });
  };

  const initThemeToggles = () => {
    document.querySelectorAll(".theme-toggle").forEach((toggle) => {
      toggle.addEventListener("click", () => {
        const nextTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        applyTheme(nextTheme, { persist: true });
      });
    });
  };

  const initConsent = () => {
    buildConsentMarkup();
    bindConsentEvents();
    if (!readConsent()) showConsentBanner();
  };

  document.addEventListener("DOMContentLoaded", () => {
    syncThemeWithConsent();
    initThemeToggles();
    initConsent();
  });
})();
