import webview

html = """
<body>
  <h1>Drop here</h1>
  <script>
    document.body.addEventListener('dragover', e => {
      e.preventDefault();
    });
    document.body.addEventListener('drop', e => {
      e.preventDefault();
      const files = Array.from(e.dataTransfer.files);
      const paths = files.map(f => f.path || f.name);
      document.body.innerHTML += '<br>Dropped: ' + paths.join(', ');
    });
  </script>
</body>
"""
webview.create_window('HTML Drop', html=html)
webview.start()
