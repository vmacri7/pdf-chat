// handle pdf upload
const pdfForm = document.getElementById('pdf-upload-form');
const pdfStatus = document.getElementById('pdf-upload-status');
const pdfFileInput = document.getElementById('pdf-file');
let uploadedPdf = null;
let selectedPdf = null;

// when a file is selected, upload it immediately
pdfFileInput.addEventListener('change', async (e) => {
    if (!pdfFileInput.files[0]) return;
    const formData = new FormData();
    formData.append('pdf_file', pdfFileInput.files[0]);
    pdfStatus.textContent = 'uploading...';
    const res = await fetch('/upload_pdf', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok) {
        pdfStatus.textContent = 'pdf uploaded!';
        uploadedPdf = data.filename;
        await fetchAndRenderPdfs();
    } else {
        pdfStatus.textContent = data.error || 'upload failed';
    }
    // reset the file input so the same file can be uploaded again if needed
    pdfFileInput.value = '';
});

// fetch and render pdf cards
const pdfCardsContainer = document.getElementById('pdf-cards-container');
async function fetchAndRenderPdfs() {
    const res = await fetch('/list_pdfs');
    const data = await res.json();
    pdfCardsContainer.innerHTML = '';
    data.pdfs.forEach(filename => {
        const card = document.createElement('div');
        card.className = 'pdf-card';
        card.textContent = filename;
        card.onclick = () => selectPdfCard(card, filename);
        if (selectedPdf === filename) {
            card.classList.add('selected');
        }
        pdfCardsContainer.appendChild(card);
    });
}

function selectPdfCard(card, filename) {
    // deselect all
    document.querySelectorAll('.pdf-card').forEach(c => c.classList.remove('selected'));
    // select this one
    card.classList.add('selected');
    selectedPdf = filename;
    // update chat header
    document.getElementById('current-pdf').textContent = filename;
    updateChatRecordBtnState();
    // clear chat messages
    document.getElementById('chat-messages').innerHTML = '';
}

// initial fetch
fetchAndRenderPdfs();

// chat record/send logic
const chatRecordBtn = document.getElementById('chat-record-btn');
const chatResponse = document.getElementById('chat-response');
let isRecording = false;
let mediaRecorder;
let audioChunks = [];

function updateChatRecordBtnState() {
    if (!selectedPdf) {
        chatRecordBtn.disabled = true;
        chatRecordBtn.textContent = 'select pdf to start!';
    } else if (isRecording) {
        chatRecordBtn.disabled = false;
        chatRecordBtn.textContent = 'press to stop';
    } else {
        chatRecordBtn.disabled = false;
        chatRecordBtn.textContent = 'press to chat';
    }
}

chatRecordBtn.addEventListener('click', async () => {
    if (!isRecording) {
        // start recording
        if (!navigator.mediaDevices) {
            showMessage('audio recording not supported', 'ai');
            return;
        }
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = async () => {
            // show user audio bubble
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            showAudioMessage(audioBlob, 'user');
            // show placeholder while thinking
            showMessage('...', 'ai', true);
            // send audio and selected pdf to /chat
            const formData = new FormData();
            formData.append('pdf_filename', selectedPdf);
            formData.append('audio_file', audioBlob, 'recording.wav');
            const res = await fetch('/chat', { method: 'POST', body: formData });
            const data = await res.json();
            // remove the placeholder
            removeLastMessageIfPlaceholder();
            if (res.ok) {
                showMessage(data.response_text, 'ai');
                if (data.tts_audio_url) {
                    showAudioMessage(data.tts_audio_url, 'ai');
                }
            } else {
                showMessage(data.error || 'chat failed', 'ai');
            }
        };
        mediaRecorder.start();
        isRecording = true;
        chatRecordBtn.classList.add('listening');
        updateChatRecordBtnState();
    } else {
        // stop recording
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            isRecording = false;
            chatRecordBtn.classList.remove('listening');
            updateChatRecordBtnState();
        }
    }
});

function showMessage(text, who, isPlaceholder = false) {
    const chatMessages = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'message' + (who === 'user' ? ' user' : '');
    msg.textContent = text;
    if (isPlaceholder) msg.dataset.placeholder = 'true';
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showAudioMessage(audio, who) {
    const chatMessages = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'message' + (who === 'user' ? ' user' : '');
    const audioElem = document.createElement('audio');
    audioElem.controls = true;
    if (typeof audio === 'string') {
        audioElem.src = audio;
    } else {
        audioElem.src = URL.createObjectURL(audio);
    }
    msg.appendChild(audioElem);
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeLastMessageIfPlaceholder() {
    const chatMessages = document.getElementById('chat-messages');
    const last = chatMessages.lastElementChild;
    if (last && last.dataset.placeholder === 'true') {
        chatMessages.removeChild(last);
    }
} 