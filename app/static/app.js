// Plain vanilla JavaScript for XRay Report AI frontend
document.addEventListener("DOMContentLoaded", () => {
  let currentReport = null;

  // DOM Elements
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const browseBtn = document.getElementById("browse-btn");
  const uploadLoading = document.getElementById("upload-loading");
  const alertBox = document.getElementById("alert-box");

  const previewSection = document.getElementById("preview-section");
  const previewMeta = document.getElementById("preview-meta");
  const xrayImage = document.getElementById("xray-image");

  const noReportPlaceholder = document.getElementById("no-report-placeholder");
  const reportForm = document.getElementById("report-form");
  const findingsInput = document.getElementById("findings-input");
  const impressionInput = document.getElementById("impression-input");
  const saveBtn = document.getElementById("save-btn");
  const approveBtn = document.getElementById("approve-btn");
  const approvedNotice = document.getElementById("approved-notice");

  const mockBadge = document.getElementById("mock-badge");
  const statusBadge = document.getElementById("status-badge");

  const historyTableBody = document.getElementById("history-table-body");
  const refreshHistoryBtn = document.getElementById("refresh-history-btn");

  // Show status notification
  function showAlert(message, type = "error") {
    alertBox.textContent = message;
    alertBox.className = `alert-box alert-${type}`;
    alertBox.classList.remove("hidden");
    if (type === "success") {
      setTimeout(() => alertBox.classList.add("hidden"), 4000);
    }
  }

  function hideAlert() {
    alertBox.classList.add("hidden");
  }

  // Drag and drop event listeners
  ["dragenter", "dragover"].forEach((event) => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((event) => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });

  browseBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", (e) => {
    if (fileInput.files.length > 0) {
      uploadFile(fileInput.files[0]);
      fileInput.value = ""; // Reset input so same file can be re-selected if desired
    }
  });

  // Upload handler
  async function uploadFile(file) {
    hideAlert();
    uploadLoading.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/reports", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed. Please check file format and try again.");
      }

      currentReport = data;
      renderReport(data);
      loadHistory();
      showAlert("Draft report created successfully!", "success");
    } catch (err) {
      showAlert(err.message || "Failed to upload and generate report.", "error");
    } finally {
      uploadLoading.classList.add("hidden");
    }
  }

  // Render report details to UI
  function renderReport(report) {
    if (!report) return;
    currentReport = report;

    // Show image preview
    previewSection.classList.remove("hidden");
    xrayImage.src = `/api/reports/${report.id}/image?t=${Date.now()}`;
    previewMeta.textContent = `${report.original_filename} (Report #${report.id})`;

    // Hide placeholder and show form
    noReportPlaceholder.classList.add("hidden");
    reportForm.classList.remove("hidden");

    // Populate findings and impression
    findingsInput.value = report.final_findings || report.ai_findings || "";
    impressionInput.value = report.final_impression || report.ai_impression || "";

    // Badges
    if (report.is_mock) {
      mockBadge.textContent = "MOCK - not a real AI result";
      mockBadge.classList.remove("hidden");
    } else {
      mockBadge.classList.add("hidden");
    }

    statusBadge.classList.remove("hidden");
    if (report.status === "approved") {
      statusBadge.textContent = "Approved";
      statusBadge.className = "badge badge-approved";

      // Read-only locking
      findingsInput.readOnly = true;
      impressionInput.readOnly = true;
      saveBtn.disabled = true;
      approveBtn.disabled = true;
      approvedNotice.classList.remove("hidden");
    } else {
      statusBadge.textContent = "Draft";
      statusBadge.className = "badge badge-draft";

      // Editable mode
      findingsInput.readOnly = false;
      impressionInput.readOnly = false;
      saveBtn.disabled = false;
      approveBtn.disabled = false;
      approvedNotice.classList.add("hidden");
    }

    highlightActiveRow(report.id);
  }

  // Save edits
  saveBtn.addEventListener("click", async () => {
    if (!currentReport || currentReport.status === "approved") return;
    hideAlert();

    const payload = {
      final_findings: findingsInput.value.trim(),
      final_impression: impressionInput.value.trim(),
    };

    try {
      const response = await fetch(`/api/reports/${currentReport.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to save edits.");
      }

      currentReport = data;
      renderReport(data);
      loadHistory();
      showAlert("Edits saved successfully!", "success");
    } catch (err) {
      showAlert(err.message, "error");
    }
  });

  // Approve report
  approveBtn.addEventListener("click", async () => {
    if (!currentReport || currentReport.status === "approved") return;
    if (!confirm("Are you sure you want to approve this report? Once approved, it cannot be modified.")) {
      return;
    }

    hideAlert();

    try {
      const response = await fetch(`/api/reports/${currentReport.id}/approve`, {
        method: "POST",
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to approve report.");
      }

      currentReport = data;
      renderReport(data);
      loadHistory();
      showAlert("Report approved successfully! It is now locked as read-only.", "success");
    } catch (err) {
      showAlert(err.message, "error");
    }
  });

  // Load previous reports history
  async function loadHistory() {
    try {
      const response = await fetch("/api/reports");
      if (!response.ok) throw new Error("Failed to load reports history.");

      const reports = await response.json();
      historyTableBody.innerHTML = "";

      if (reports.length === 0) {
        historyTableBody.innerHTML = `
          <tr>
            <td colspan="6" class="text-center text-muted">No reports found yet. Upload an image above!</td>
          </tr>
        `;
        return;
      }

      reports.forEach((rep) => {
        const tr = document.createElement("tr");
        tr.dataset.reportId = rep.id;
        if (currentReport && currentReport.id === rep.id) {
          tr.classList.add("active-row");
        }

        const dateStr = new Date(rep.created_at).toLocaleString();
        const badgeClass = rep.status === "approved" ? "badge-approved" : "badge-draft";
        const statusLabel = rep.status === "approved" ? "Approved" : "Draft";

        tr.innerHTML = `
          <td>#${rep.id}</td>
          <td><strong>${escapeHtml(rep.original_filename)}</strong></td>
          <td>${dateStr}</td>
          <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
          <td><small class="text-muted">${escapeHtml(rep.engine_name)}</small></td>
          <td><button type="button" class="btn btn-sm btn-outline open-report-btn">Open</button></td>
        `;

        tr.addEventListener("click", () => fetchAndDisplayReport(rep.id));
        historyTableBody.appendChild(tr);
      });
    } catch (err) {
      historyTableBody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center text-danger">${err.message}</td>
        </tr>
      `;
    }
  }

  async function fetchAndDisplayReport(id) {
    hideAlert();
    try {
      const response = await fetch(`/api/reports/${id}`);
      if (!response.ok) throw new Error("Could not fetch selected report.");
      const data = await response.json();
      renderReport(data);
    } catch (err) {
      showAlert(err.message, "error");
    }
  }

  function highlightActiveRow(id) {
    const rows = historyTableBody.querySelectorAll("tr");
    rows.forEach((row) => {
      if (row.dataset.reportId == id) {
        row.classList.add("active-row");
      } else {
        row.classList.remove("active-row");
      }
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  refreshHistoryBtn.addEventListener("click", loadHistory);

  // Initialize
  loadHistory();
});
