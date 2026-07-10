/** Live, server-backed filtering for the material table. */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#material-filters");
  const search = document.querySelector("#material-search");
  if (!form || !search) return;

  let timer;
  let activeRequest;

  async function refreshTable() {
    // Cancel an older request when the user types again before it completes.
    activeRequest?.abort();
    activeRequest = new AbortController();

    const query = new URLSearchParams(new FormData(form));
    // Build from the action's pathname only. Using the full current URL here
    // can retain the previous query string after history.replaceState(), which
    // makes live filtering work once and then generate malformed URLs.
    const actionUrl = new URL(form.action, window.location.origin);
    const url = `${actionUrl.pathname}?${query.toString()}`;
    const table = document.querySelector(".table-wrap");
    table?.setAttribute("aria-busy", "true");

    try {
      const response = await fetch(url, {
        headers: { "X-Requested-With": "fetch" },
        signal: activeRequest.signal,
      });
      if (!response.ok) throw new Error(`Filtering failed (${response.status})`);

      const documentCopy = new DOMParser().parseFromString(await response.text(), "text/html");
      const newTable = documentCopy.querySelector(".table-wrap");
      const newCount = documentCopy.querySelector("#result-count");
      if (!newTable || !newCount) throw new Error("Filtering returned an incomplete page");

      table.replaceWith(newTable);
      document.querySelector("#result-count").textContent = newCount.textContent;
      history.replaceState(null, "", url);
    } catch (error) {
      if (error.name !== "AbortError") console.error(error);
      table?.removeAttribute("aria-busy");
    }
  }

  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(refreshTable, 250);
  });

  // Dropdown filters benefit from the same in-place update.
  form.querySelectorAll("select").forEach((select) => {
    select.addEventListener("change", refreshTable);
  });

  async function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      if (!document.execCommand("copy")) throw new Error("Copy command was rejected");
    } finally {
      textarea.remove();
    }
  }

  document.addEventListener("change", async (event) => {
    const control = event.target;
    if (!(control instanceof HTMLInputElement) || !control.classList.contains("inline-save")) return;
    const inlineForm = control.form;
    if (!inlineForm) return;

    const payload = new FormData(inlineForm);
    const linkedControls = document.querySelectorAll(`[form="${inlineForm.id}"]`);
    linkedControls.forEach((item) => {
      if (item instanceof HTMLInputElement) item.disabled = true;
    });

    try {
      const response = await fetch(inlineForm.action, {
        method: inlineForm.method || "post",
        body: payload,
        headers: { "X-Requested-With": "fetch" },
      });
      if (!response.ok) throw new Error(`Inline save failed (${response.status})`);
    } catch (error) {
      console.error(error);
      // If a save fails, refresh the visible filtered table from the server so
      // the controls return to the persisted database state.
      refreshTable();
    } finally {
      linkedControls.forEach((item) => {
        if (item instanceof HTMLInputElement) item.disabled = false;
      });
    }
  });

  document.addEventListener("click", async (event) => {
    const button = event.target.closest(".copy-name-button");
    if (!(button instanceof HTMLButtonElement)) return;

    const text = button.dataset.copyText || "";
    if (!text) return;

    try {
      await copyToClipboard(text);
      button.classList.add("copied");
      button.setAttribute("aria-label", `Copied ${text}`);
      setTimeout(() => {
        button.classList.remove("copied");
        button.setAttribute("aria-label", `Copy ${text}`);
      }, 1200);
    } catch (error) {
      console.error(error);
      button.classList.add("copy-failed");
      setTimeout(() => button.classList.remove("copy-failed"), 1200);
    }
  });
});
