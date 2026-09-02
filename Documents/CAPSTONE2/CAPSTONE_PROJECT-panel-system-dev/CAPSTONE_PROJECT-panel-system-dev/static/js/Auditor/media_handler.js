(function () {
    "use strict";

    function getEl(id) {
        return document.getElementById(id);
    }

    function getScreenElements(screenId) {
        const screenName = screenId ? screenId.replace("EvidenceScreen", "").toLowerCase() : "";
        if (screenName === "membershipfee") {
            return {
                badge: getEl("membershipFeeEvidenceBadge"),
                title: getEl("membershipFeeEvidenceTitle"),
                desc: getEl("membershipFeeEvidenceDesc")
            };
        } else if (screenName === "aid") {
            return {
                badge: getEl("aidEvidenceBadge"),
                title: getEl("aidEvidenceTitle"),
                desc: getEl("aidEvidenceDesc")
            };
        } else {
            return {
                badge: getEl("paymentEvidenceBadge"),
                title: getEl("paymentEvidenceTitle"),
                desc: getEl("paymentEvidenceDesc")
            };
        }
    }

    function isImageType(fileType) {
        if (!fileType) return false;
        const imageTypes = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml", "image/bmp", "image/tiff"];
        return imageTypes.includes(fileType.toLowerCase());
    }

    function isPdfType(fileType) {
        if (!fileType) return false;
        return fileType.toLowerCase() === "application/pdf";
    }

    function getFileExtension(fileType) {
        if (!fileType) return "file";
        const map = {
            "application/pdf": "pdf",
            "application/msword": "doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.ms-excel": "xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/zip": "zip",
            "application/x-zip-compressed": "zip"
        };
        return map[fileType.toLowerCase()] || "file";
    }

    function getFileIconSvg(ext) {
        const icons = {
            pdf: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>`,
            doc: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>`,
            docx: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>`,
            xls: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>`,
            xlsx: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>`,
            zip: `<path d="M21 16v2.5a2.5 2.5 0 0 1-2.5 2.5H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5"></path><path d="M17 2v6h6"></path>`,
            file: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline>`
        };
        return icons[ext] || icons.file;
    }

    function renderMediaPreview(fileUrl, fileType, fileName, screenId) {
        const screen = getEl(screenId || "paymentEvidenceScreen");
        const elements = getScreenElements(screenId);
        const { badge, title, desc } = elements;

        if (!screen) return;

        if (!fileUrl) {
            renderEmptyState(screenId);
            return;
        }

        screen.innerHTML = "";
        screen.style.borderColor = "#fbc02d";
        /* EDIT: Remove the line below if you don't want auto-fit enabled */
        screen.classList.add("auto-fit-media");

        const wrapperStyle = "display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;height:100%;max-height:70vh;overflow:auto;box-sizing:border-box;";
        const contentWrapper = document.createElement("div");
        contentWrapper.style = wrapperStyle;

        if (isImageType(fileType)) {
            if (badge) badge.innerText = "IMAGE ATTACHMENT";
            if (title) title.innerText = fileName || "Image Preview";
            if (desc) desc.innerText = "Evidence image from Treasurer submission.";

            const img = document.createElement("img");
            img.src = fileUrl;
            img.alt = fileName || "Evidence image";
            img.style = "max-width:100%;max-height:70vh;object-fit:contain;cursor:pointer;border-radius:8px;";
            img.onerror = function () {
                renderErrorState("Unable to load image. File may be corrupted or unavailable.", screenId);
            };
            img.onclick = function () {
                window.open(fileUrl, "_blank");
            };
            /* EDIT BELOW: Auto-detect image aspect ratio and apply to container */
            img.onload = function () {
                if (!screen) return;
                if (!screen.contains(this)) return;
                const naturalW = this.naturalWidth || 1;
                const naturalH = this.naturalHeight || 1;
                const ratio = (naturalW / naturalH).toFixed(4);
                screen.style.aspectRatio = ratio;
                /* EDIT: Adjust the CSS max-width/max-height in the HTML style block to control final rendered size */
            };
            contentWrapper.appendChild(img);
        } else {
            const docType = getFileExtension(fileType).toUpperCase() || "FILE";
            if (badge) badge.innerText = "DOCUMENT ATTACHMENT";
            if (title) title.innerText = "Document Type: " + docType;
            if (desc) desc.innerText = fileName || "Non-viewable document. Download or open in new tab to inspect.";

            const openBtn = document.createElement("a");
            openBtn.href = fileUrl;
            openBtn.target = "_blank";
            openBtn.rel = "noopener noreferrer";
            openBtn.innerText = "Open in new tab";
            /* EDIT: Uniform slim rounded button — adjust padding/width below */
            openBtn.style = "display:inline-flex;align-items:center;justify-content:center;background:#1b5e20;color:white;padding:8px 24px;border-radius:20px;font-weight:600;font-size:0.8rem;text-decoration:none;cursor:pointer;transition:0.2s;min-width:180px;";
            openBtn.onmouseover = function () { this.style.background = "#2e7d32"; };
            openBtn.onmouseout = function () { this.style.background = "#1b5e20"; };

            const downloadBtn = document.createElement("a");
            downloadBtn.href = fileUrl;
            downloadBtn.download = fileName || "download";
            downloadBtn.innerText = "Download Document";
            /* EDIT: Uniform slim rounded button — match openBtn styling here */
            downloadBtn.style = "display:inline-flex;align-items:center;justify-content:center;background:#fbc02d;color:#1b5e20;padding:6px 16px;border-radius:20px;font-weight:600;font-size:0.75rem;text-decoration:none;cursor:pointer;transition:0.2s;min-width:180px;";
            downloadBtn.onmouseover = function () { this.style.background = "#f9a825"; };
            downloadBtn.onmouseout = function () { this.style.background = "#fbc02d"; };

            const btnRow = document.createElement("div");
            btnRow.style = "margin-top:16px;display:inline-flex;flex-wrap:wrap;gap:10px;justify-content:center;";
            btnRow.appendChild(openBtn);
            btnRow.appendChild(downloadBtn);

            contentWrapper.appendChild(btnRow);
        }

        screen.appendChild(contentWrapper);
    }

    function renderEmptyState(screenId) {
        const screen = getEl(screenId || "paymentEvidenceScreen");
        const elements = getScreenElements(screenId);
        const { title, desc } = elements;

        if (!screen) return;

        screen.style.borderColor = "#2e7d32";
        /* EDIT: Reset aspect ratio when switching entries so empty state uses default container shape */
        screen.style.aspectRatio = "";
        /* EDIT END */

        const screenName = screenId ? screenId.replace("EvidenceScreen", "").toLowerCase() : "";

        screen.innerHTML = `
            <svg viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
            </svg>
            <p style="font-weight: 600" id="${screenName}EvidenceTitle">No Supporting Document Found</p>
        `;

        if (title) title.innerText = "No Supporting Document Found";
        if (desc) desc.innerText = "";
    }

    function renderErrorState(message, screenId) {
        const screen = getEl(screenId || "paymentEvidenceScreen");
        const elements = getScreenElements(screenId);
        const { badge, title, desc } = elements;

        if (!screen) return;

        screen.style.borderColor = "#e53935";
        /* EDIT: Reset aspect ratio on error state so container returns to default shape */
        screen.style.aspectRatio = "";
        /* EDIT END */

        screen.innerHTML = `
            <svg viewBox="0 0 24 24" style="fill:#e53935;">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
            </svg>
            <p style="font-weight: 600;color:#e53935;">
                Failed to Load Evidence
            </p>
            <p style="font-size: 0.8rem;opacity:0.8;margin-top:5px">
                ${message || "Unable to retrieve supporting document."}
            </p>
        `;

        if (title) title.innerText = "Failed to Load Evidence";
        if (desc) desc.innerText = message || "Unable to retrieve supporting document.";
    }

    async function fetchMediaForRecord(recordId, modelType, screenId) {
        if (!recordId) {
            renderEmptyState(screenId);
            return null;
        }

        const endpoint = `/api/auditor/supporting-proof/${encodeURIComponent(modelType || "monthly_dues")}/${encodeURIComponent(recordId)}/`;

        try {
            const response = await fetch(endpoint, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("application/json")) {
                throw new Error("Server returned an unexpected response. Please try again.");
            }

            const data = await response.json();

            if (data && data.ok && data.proof) {
                return {
                    fileUrl: data.proof.file_url,
                    fileType: data.proof.file_type,
                    fileName: data.proof.file_name
                };
            }

            renderEmptyState(screenId);
            return null;
        } catch (error) {
            renderErrorState(error.message || "Error fetching supporting proof.", screenId);
            return null;
        }
    }

    function loadMediaPreview(fileUrl, fileType, fileName, screenId) {
        renderMediaPreview(fileUrl, fileType, fileName, screenId);
    }

    window.renderMediaPreview = renderMediaPreview;
    window.renderEmptyState = renderEmptyState;
    window.fetchMediaForRecord = fetchMediaForRecord;
    window.loadMediaPreview = loadMediaPreview;

})();