// file_queue.js - Shared file upload queue for Treasurer dashboard

window.FileQueue = (function () {
  var queues = {};

  function isPreviewable(file) {
    return file.type.startsWith("image/") || file.type === "application/pdf";
  }

  function confirmNonPreviewable(file) {
    var ext = file.name.split(".").pop();
    return new Promise(function (resolve) {
      Swal.fire({
        title: "Unsupported File for Preview",
        html:
          'The file <strong>' +
          file.name +
          "</strong> (." +
          ext +
          ') is accepted but cannot be previewed within the system. Users will need to download the file to view its contents.<br><br>For in-system preview support, please convert the file to PDF before uploading. PDF files can be viewed directly using your browser\'s native PDF viewer.',
        icon: "info",
        showCancelButton: true,
        confirmButtonText: "I Understand, Continue Upload",
        cancelButtonText: "Cancel",
        confirmButtonColor: "#1b5e20",
        cancelButtonColor: "#e53935",
        reverseButtons: true,
        customClass: { popup: "swal-rounded" },
      }).then(function (r) {
        resolve(r.isConfirmed);
      });
    });
  }

  function render(key) {
    var q = queues[key];
    if (!q) return;
    var container = document.getElementById(q.containerId);
    if (!container) return;
    container.innerHTML = "";
    for (var fi = 0; fi < q.files.length; fi++) {
      (function (fiIdx) {
        var file = q.files[fiIdx];
        var div = document.createElement("div");
        div.className = "file-queue-thumb";
        div.title = file.name;
        div.onclick = function () {
          preview(key, fiIdx);
        };
        if (file.type.startsWith("image/")) {
          var img = document.createElement("img");
          img.src = URL.createObjectURL(file);
          img.onload = function () {
            URL.revokeObjectURL(this.src);
          };
          div.appendChild(img);
        } else {
          var iconDiv = document.createElement("div");
          iconDiv.className = "fq-icon";
          iconDiv.innerHTML =
            file.type === "application/pdf"
              ? '<i class="fa-solid fa-file-pdf"></i>'
              : '<i class="fa-solid fa-file-word"></i>';
          div.appendChild(iconDiv);
        }
        var removeBtn = document.createElement("button");
        removeBtn.className = "fq-remove";
        removeBtn.innerHTML = "&times;";
        removeBtn.title = "Remove file";
        removeBtn.onclick = function (e) {
          e.stopPropagation();
          remove(key, fiIdx);
        };
        div.appendChild(removeBtn);
        container.appendChild(div);
      })(fi);
    }
  }

  function preview(key, idx) {
    var q = queues[key];
    if (!q || idx >= q.files.length) return;
    var file = q.files[idx];
    var url = URL.createObjectURL(file);
    var html = "";
    var width = "600px";
    if (file.type.startsWith("image/")) {
      html =
        '<img src="' +
        url +
        '" style="max-width:100%;max-height:70vh;border-radius:8px;" />';
    } else if (file.type === "application/pdf") {
      width = "90vw";
      html =
        '<iframe src="' +
        url +
        '" style="width:100%;height:80vh;border:none;border-radius:8px;"></iframe>';
    } else {
      html =
        '<div style="text-align:center;padding:20px;">' +
        '<i class="fa-solid fa-file-word" style="font-size:4rem;color:#1565c0;"></i>' +
        '<p style="margin-top:16px;font-weight:600;word-break:break-all;">' +
        file.name +
        "</p>" +
        '<p style="margin-top:8px;color:#757575;font-size:0.85rem;">Preview not available for this file type.</p>' +
        '<button onclick="var a=document.createElement(\'a\');a.href=\'' +
        url +
        "';a.download='" +
        file.name.replace(/'/g, "\\'") +
        "';a.click();\" style=\"margin-top:12px;padding:8px 24px;background:#1b5e20;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:0.9rem;\">Download File</button>" +
        "</div>";
    }
    Swal.fire({
      html: html,
      width: width,
      showCloseButton: true,
      showConfirmButton: false,
      customClass: { popup: "swal-rounded" },
      didClose: function () {
        URL.revokeObjectURL(url);
      },
    });
  }

  return {
    init: function (key, opts) {
      if (queues[key]) return;
      queues[key] = {
        files: [],
        inputId: opts.inputId,
        containerId: opts.containerId,
        maxFiles: opts.maxFiles || 1,
        accept: opts.accept || "image/*,.pdf,.docx",
        onChange: opts.onChange || null,
      };
    },

    handleInput: async function (key) {
      var q = queues[key];
      if (!q) return;
      var inputEl = document.getElementById(q.inputId);
      if (!inputEl || !inputEl.files) return;
      for (var fi = 0; fi < inputEl.files.length; fi++) {
        var file = inputEl.files[fi];
        if (q.maxFiles === 1) {
          q.files = [];
        }
        if (q.files.length >= q.maxFiles) {
          showToast("Maximum of " + q.maxFiles + " file(s).", true);
          break;
        }
        var dup = false;
        for (var di = 0; di < q.files.length; di++) {
          if (
            q.files[di].name === file.name &&
            q.files[di].size === file.size
          ) {
            dup = true;
            break;
          }
        }
        if (dup) continue;
        if (!isPreviewable(file)) {
          var ok = await confirmNonPreviewable(file);
          if (!ok) continue;
        }
        q.files.push(file);
      }
      inputEl.value = "";
      render(key);
      if (q.onChange) q.onChange(key, q.files);
    },

    remove: function (key, idx) {
      var q = queues[key];
      if (!q || idx >= q.files.length) return;
      q.files.splice(idx, 1);
      render(key);
      if (q.onChange) q.onChange(key, q.files);
    },

    preview: function (key, idx) {
      preview(key, idx);
    },

    getFiles: function (key) {
      var q = queues[key];
      return q ? q.files : [];
    },

    clear: function (key) {
      var q = queues[key];
      if (!q) return;
      q.files = [];
      render(key);
      if (q.onChange) q.onChange(key, q.files);
    },

    pushFiles: function (key, fileArray) {
      var q = queues[key];
      if (!q) return;
      for (var fi = 0; fi < fileArray.length; fi++) {
        q.files.push(fileArray[fi]);
      }
      render(key);
      if (q.onChange) q.onChange(key, q.files);
    },
  };
})();
