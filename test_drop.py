import webview

def on_drop(files):
    print("Dropped:", files)
    window.evaluate_js(f"document.body.innerHTML += '<br>Dropped: {files}'")

window = webview.create_window('Drag Drop Test', html='<h1>Drop files here</h1>')
window.events.dropped += on_drop
webview.start()
