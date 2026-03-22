<script>
  const version = import.meta.env.VITE_APP_VERSION || 'dev';
  const year = new Date().getFullYear();
</script>

<footer class="app-footer">
  <div class="footer-inner">
    <p class="footer-copyright">© {year} David D Tessier. All rights reserved.</p>
    <p class="footer-meta">Version <span class="footer-version">{version}</span></p>
  </div>
</footer>
