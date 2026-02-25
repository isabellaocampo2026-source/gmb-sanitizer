document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('sanitizeForm');
    const fileInput = document.getElementById('fileInput');
    const dropzone = document.getElementById('dropzone');
    const fileList = document.getElementById('fileList');
    const submitBtn = document.getElementById('submitBtn');
    const progress = document.getElementById('progress');
    const progressText = document.getElementById('progressText');
    const citySelect = document.getElementById('city');
    const locPreview = document.getElementById('locationPreview');
    const locText = document.getElementById('locText');
    const statusMsg = document.getElementById('statusMsg');

    // Set default dates (last 30 days to today)
    const today = new Date();
    const monthAgo = new Date(today);
    monthAgo.setDate(today.getDate() - 30);
    document.getElementById('date_to').value = today.toISOString().split('T')[0];
    document.getElementById('date_from').value = monthAgo.toISOString().split('T')[0];

    // ---- Drag & Drop ----
    ['dragenter', 'dragover'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });
    dropzone.addEventListener('drop', e => {
        fileInput.files = e.dataTransfer.files;
        updateFileList();
    });
    fileInput.addEventListener('change', updateFileList);

    function updateFileList() {
        fileList.innerHTML = '';
        const files = fileInput.files;
        if (files.length === 0) {
            submitBtn.disabled = true;
            return;
        }
        for (const f of files) {
            const tag = document.createElement('span');
            tag.className = 'file-tag';
            const sizeMB = (f.size / 1024 / 1024).toFixed(1);
            tag.textContent = `${f.name} (${sizeMB} MB)`;
            fileList.appendChild(tag);
        }
        submitBtn.disabled = false;
        hideStatus();
    }

    // ---- City change -> show preview ----
    citySelect.addEventListener('change', async () => {
        const city = citySelect.value;
        if (!city) {
            locPreview.style.display = 'none';
            updateKeywordPreview();
            return;
        }
        try {
            const resp = await fetch('/api/cities');
            const data = await resp.json();
            if (data[city]) {
                const c = data[city];
                locText.textContent = `📍 ${city}, ${c.department} — ${c.lat.toFixed(4)}°, ${c.lon.toFixed(4)}° — Alt: ${c.altitude}m`;
                locPreview.style.display = 'block';
            }
        } catch (e) {
            console.error(e);
        }
        updateKeywordPreview();
    });

    // ---- Keyword preview ----
    const keywordInput = document.getElementById('keyword');
    const keywordPreview = document.getElementById('keywordPreview');

    function slugify(text) {
        return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .toLowerCase().trim()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/[\s_-]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'foto';
    }

    function updateKeywordPreview() {
        const kw = keywordInput.value.trim();
        if (!kw) {
            keywordPreview.textContent = '';
            return;
        }
        const slug = slugify(kw);
        const city = citySelect.value;
        const citySlug = city ? slugify(city) : '';
        const example = citySlug ? `${slug}-${citySlug}-1.jpg` : `${slug}-1.jpg`;
        keywordPreview.textContent = `📄 Archivo: ${example}`;
    }

    keywordInput.addEventListener('input', updateKeywordPreview);

    // ---- Status messages ----
    function showStatus(message, type) {
        statusMsg.textContent = message;
        statusMsg.className = 'status-msg status-' + type;
        statusMsg.style.display = 'block';
    }

    function hideStatus() {
        statusMsg.style.display = 'none';
    }

    // ---- Form submit ----
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideStatus();

        if (fileInput.files.length === 0) {
            showStatus('⚠️ Selecciona al menos una foto antes de continuar.', 'error');
            return;
        }

        // Validate city or coords
        const city = citySelect.value;
        const manualLat = form.querySelector('[name="manual_lat"]').value.trim();
        const manualLon = form.querySelector('[name="manual_lon"]').value.trim();
        if (!city && !manualLat && !manualLon) {
            showStatus('⚠️ Selecciona una ciudad o ingresa coordenadas manuales.', 'error');
            return;
        }

        submitBtn.disabled = true;
        progress.style.display = 'block';
        progressText.textContent = `Procesando ${fileInput.files.length} foto(s)... Esto puede tardar unos segundos.`;

        const formData = new FormData(form);
        if (!document.getElementById('randomPerPhoto').checked) {
            formData.set('random_device_per_photo', 'false');
        }

        try {
            const resp = await fetch('/api/sanitize', { method: 'POST', body: formData });

            if (!resp.ok) {
                let errorMsg = 'Error del servidor';
                try {
                    const err = await resp.json();
                    errorMsg = err.detail || errorMsg;
                } catch (_) { }
                throw new Error(errorMsg);
            }

            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const disposition = resp.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="?(.+?)"?$/);
            a.download = match ? match[1] : 'gmb_sanitized.zip';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);

            // Read processing results from headers
            const gmbProcessed = resp.headers.get('X-GMB-Processed') || '0';
            const gmbTotal = resp.headers.get('X-GMB-Total') || String(fileInput.files.length);
            const gmbErrors = resp.headers.get('X-GMB-Errors') || '';

            if (parseInt(gmbProcessed) === parseInt(gmbTotal)) {
                showStatus(`✅ ¡Listo! Se procesaron ${gmbProcessed}/${gmbTotal} foto(s). El archivo ZIP se descargó automáticamente.`, 'success');
            } else if (parseInt(gmbProcessed) > 0) {
                showStatus(`⚠️ Se procesaron ${gmbProcessed}/${gmbTotal} foto(s). Algunas fallaron: ${gmbErrors}`, 'error');
            } else {
                showStatus(`❌ No se pudo procesar ninguna foto (0/${gmbTotal}). Errores: ${gmbErrors}`, 'error');
            }

        } catch (err) {
            showStatus('❌ Error: ' + err.message, 'error');
        } finally {
            submitBtn.disabled = false;
            progress.style.display = 'none';
        }
    });

    // ---- Verify section ----
    const verifyInput = document.getElementById('verifyInput');
    const verifyResult = document.getElementById('verifyResult');

    verifyInput.addEventListener('change', async () => {
        const file = verifyInput.files[0];
        if (!file) return;
        const fd = new FormData();
        fd.append('file', file);
        verifyResult.style.display = 'block';
        verifyResult.textContent = 'Leyendo EXIF...';
        try {
            const resp = await fetch('/api/verify', { method: 'POST', body: fd });
            const data = await resp.json();
            if (data.error) {
                verifyResult.textContent = '⚠️ ' + data.error;
            } else {
                verifyResult.textContent = JSON.stringify(data, null, 2);
            }
        } catch (err) {
            verifyResult.textContent = 'Error: ' + err.message;
        }
    });
});
