document.addEventListener("DOMContentLoaded", () => {
  const cutter = document.querySelector("#primary-cutter");
  const toolField = document.querySelector("#primary-tool-field");
  if (!cutter || !toolField) return;

  const updateToolVisibility = () => {
    const needsTool = cutter.value === "CNC" || cutter.value === "JWEI";
    toolField.hidden = !needsTool;
    toolField.querySelector("input").disabled = !needsTool;
  };

  cutter.addEventListener("change", updateToolVisibility);
  updateToolVisibility();
});
