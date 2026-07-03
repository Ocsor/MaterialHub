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
});
