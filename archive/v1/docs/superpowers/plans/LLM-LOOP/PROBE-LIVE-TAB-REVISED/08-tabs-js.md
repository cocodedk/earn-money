### File 8: `static/tabs.js` (NEW — tab switching)

```javascript
// Tab switching for RECON / PROBE dashboard

document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab');
    
    // Restore from hash
    const hash = location.hash.replace('#', '') || 'recon';
    switchTab(hash);
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            location.hash = tabId;
            switchTab(tabId);
        });
    });
    
    function switchTab(tabId) {
        // Update tab buttons
        tabs.forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tabId);
        });
        
        // Show/hide tab content
        document.querySelectorAll('[id^="tab-"]').forEach(el => {
            el.hidden = el.id !== `tab-${tabId}`;
        });
    }
});
```

