
function getBubbleHTML(text, isUser, id){
    if(isUser){
        return `
        <span> ${text}</span>
        <div class="msg-actions">
            <button class="action" id="copy-btn" title="Copy Message"  onclick="copyMsg('msg-${id}')"> <i class="fas fa-copy"></i></button>
            <button class="action" id="retry-btn" title="Retry Message" onclick="retryMsg('msg-${id}')"> <i class="fas fa-refresh"></i></button>

        </div>
        
        `
    }
    else{
        return `
        <span> ${text}</span>
        <div class="msg-actions -ai">
            <button class="action" id="report-btn" onclick="reportMsg('msg-${id}')" title="Report Message"> <i class="fas fa-flag"></i></button>
            <button class="action" id="copy-btn"  onclick="copyMsg('msg-${id}')" title="Copy Message"> <i class="fas fa-copy"></i></button>
            <button class="action" title="Share Message" onclick="shareMsg('msg-${id}')"> <i class="fas fa-share"></i></button>

        </div>
        
        `

    }
}

function makeId() {
    return crypto.randomUUID();
}
function getCookie(name) {
    let value = `; ${document.cookie}`;
    let parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function setCookie(name, value, days = 365) {
    const d = new Date();
    d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${name}=${value};expires=${d.toUTCString()};path=/`;
}

window.makeId = makeId
window.setCookie = setCookie
window.getBubbleHTML = getBubbleHTML
window.getCookie = getCookie


function copyMsg(id){
    const msg = document.querySelector(`#${id}`)
    if(!msg){
        return alert.error("Message not yet initialized")
    }
    navigator.clipboard.writeText(msg.textContent.trim())
    const copyBtn = msg.querySelector('#copy-btn')
    copyBtn.innerHTML = '<i class="fas fa-check"></i>'
    setTimeout(() => {
    copyBtn.innerHTML = '<i class="fas fa-copy"></i>'

    }, 3000);

}
function retryMsg(id){
    const msg = document.querySelector(`#${id}`)
    if(!msg){
        return alert.error("Message not yet initialized")
    }
    const i = msg.querySelector('#retry-btn i')
    i.classList.add('fa-spin')
    
    const input = document.querySelector('#query-input')
    const sbtn = document.querySelector('.send-btn')
    if(!msg.textContent.trim()){
        return alert.error("Message empty")
    }

    input.value = msg.textContent.trim()

    setTimeout(() => {
        sbtn.click()   
        i.classList.remove('fa-spin')     
    }, 500);
}
function reportMsg(id){
    const msg = document.querySelector(`#${id}`)
    if(!msg){
        return alert.error("Message not yet initialized")
    }
    const rid = String(msg.getAttribute('ref')).replace('msg-', '')
    id = String(id).replace('msg-', '')

    const btn = msg.querySelector('#report-btn')
    const i = msg.querySelector('#report-btn i')
    btn.disabled = true
    i.className = 'fas fa-refresh fa-spin'
    

    fetch(`${window.baseUrl}/report`, {
        method:'POST',
        headers:{
            'Content-Type':'application/json'
        },
        body:JSON.stringify({'rid':rid, 'id':id, 'text':msg.textContent.trim()})
    })
        .then(r=>r.json())
        .then(data=>{
         btn.disabled = false
        i.className= 'fas fa-flag'
            console.log(data)
        })
        .catch(err=>{
             btn.disabled = false
             i.className= 'fas fa-flag'

            alert.error('Connection error: ' + err.message)
        })
  
}
function shareMsg(id){
    navigator.canShare({'text':window.location.origin + '/msg/?msg=' + id})
}