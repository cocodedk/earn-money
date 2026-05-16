### File 10: `index.html` (MODIFIED — add PROBE tab)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pentest Dashboard</title>
    <link rel="stylesheet" href="/static/tokens.css">
    <link rel="stylesheet" href="/static/dashboard.css">
    <link rel="stylesheet" href="/static/probe.css">
</head>
<body>
    <div class="dashboard">
        <h1>Pentest Probe Dashboard</h1>
        
        <!-- Tab navigation -->
        <nav class="tabs" role="tablist">
            <button class="tab active" data-tab="recon">RECON</button>
            <button class="tab" data-tab="probe">PROBE</button>
        </nav>
        
        <!-- RECON tab -->
        <div id="tab-recon">
            <h2 class="rule">Reconnaissance</h2>
            <!-- existing recon content -->
        </div>
        
        <!-- PROBE tab -->
        <div id="tab-probe" hidden>
            <section id="probe-panel">
                <h2 class="rule">Live Probe</h2>
                
                <form id="probe-form">
                    <input 
                        type="url" 
                        id="probe-url" 
                        placeholder="https://target.example.com"
                        required
                    >
                    <input 
                        type="text" 
                        id="probe-roe" 
                        placeholder="roe/local-lab.yaml"
                        value="roe/local-lab.yaml"
                    >
                    <button type="submit" id="probe-run-btn">▶ Run Probe</button>
                </form>
                
                <div id="probe-status">Ready</div>
                
                <div id="probe-timeline">
                    <!-- Turn cards appear here -->
                </div>
            </section>
        </div>
    </div>
    
    <script src="/static/tabs.js"></script>
    <script src="/static/dashboard.js"></script>
    <script src="/static/probe.js"></script>
</body>
</html>
```

