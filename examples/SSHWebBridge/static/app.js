(function () {
    var token = document.getElementById('token');
    var status = document.getElementById('status');
    var output = document.getElementById('output');
    var targetSelect = document.getElementById('target');
    var serviceSelect = document.getElementById('service');
    var macroSelect = document.getElementById('macros');
    var targetActions = {};

    function saveToken(value) {
        try { window.sessionStorage.setItem('sshwb-token', value); } catch (ignore) { }
    }
    function savedToken() {
        try { return window.sessionStorage.getItem('sshwb-token') || ''; } catch (ignore) { return ''; }
    }
    function showError(message) {
        status.innerHTML = '';
        status.appendChild(document.createTextNode(message));
        status.className = 'status danger';
    }
    function request(path, payload, callback) {
        if (!token.value.replace(/^\s+|\s+$/g, '')) {
            callback('Enter the gateway token first.');
            return;
        }
        var xhr = new XMLHttpRequest();
        xhr.open(payload ? 'POST' : 'GET', path, true);
        xhr.setRequestHeader('Authorization', 'Bearer ' + token.value.replace(/^\s+|\s+$/g, ''));
        if (payload) xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            var data;
            try { data = JSON.parse(xhr.responseText); } catch (ignore) { callback('Invalid gateway response.'); return; }
            if (xhr.status < 200 || xhr.status >= 300) { callback(data.error || ('HTTP ' + xhr.status)); return; }
            callback(null, data);
        };
        xhr.onerror = function () { callback('Network error. Check gateway address and connection.'); };
        xhr.send(payload ? JSON.stringify(payload) : null);
    }
    function clearOptions(select, firstText) {
        while (select.options.length) select.remove(0);
        select.options.add(new Option(firstText, ''));
    }
    function drawMacros() {
        while (macroSelect.firstChild) macroSelect.removeChild(macroSelect.firstChild);
        var actions = targetActions[targetSelect.value] || [];
        if (!actions.length) {
            macroSelect.appendChild(document.createTextNode('No macros configured for this target.'));
            return;
        }
        for (var i = 0; i < actions.length; i++) {
            var button = document.createElement('button');
            button.appendChild(document.createTextNode(actions[i].label));
            button.setAttribute('data-macro-id', actions[i].id);
            button.onclick = (function (action) {
                return function () {
                    var confirmation = null;
                    if (action.confirm) {
                        confirmation = window.prompt('Type CONFIRM to run ' + action.label);
                        if (confirmation !== 'CONFIRM') return;
                    }
                    run(action.id, null, confirmation);
                };
            }(actions[i]));
            macroSelect.appendChild(button);
        }
    }
    function connect() {
        status.innerHTML = 'Connecting…';
        request('/api/targets', null, function (err, data) {
            if (err) { showError(err); return; }
            clearOptions(targetSelect, 'Choose server');
            clearOptions(serviceSelect, 'Select allowed service');
            var services = {};
            for (var i = 0; i < data.targets.length; i++) {
                var target = data.targets[i];
                targetSelect.options.add(new Option(target.label, target.id));
                targetActions[target.id] = target.actions || [];
                for (var j = 0; j < (target.services || []).length; j++) services[target.services[j]] = true;
            }
            for (var name in services) if (services.hasOwnProperty(name)) serviceSelect.options.add(new Option(name, name));
            request('/api/actions', null, function (actionError, actions) {
                if (actionError) { showError(actionError); return; }
                status.innerHTML = 'Connected · ' + data.targets.length + ' target(s) · ' + actions.actions.length + ' actions';
                status.className = 'status';
                drawMacros();
            });
        });
    }
    function run(action, service, confirmText) {
        if (!targetSelect.value) { showError('Choose a server first.'); return; }
        status.innerHTML = 'Running…';
        output.innerHTML = 'Waiting for gateway…';
        request('/api/run', { target: targetSelect.value, action: action, service: service, confirm: confirmText }, function (err, data) {
            if (err) { showError(err); output.innerHTML = ''; output.appendChild(document.createTextNode(err)); return; }
            output.innerHTML = '';
            output.appendChild(document.createTextNode(data.output || '(no output)'));
            status.innerHTML = 'Completed · exit ' + data.exit_code + ' · ' + data.elapsed_ms + ' ms';
            status.className = 'status';
        });
    }

    document.getElementById('connect').onclick = connect;
    targetSelect.onchange = drawMacros;
    document.getElementById('forget').onclick = function () {
        token.value = '';
        saveToken('');
        status.innerHTML = 'Token cleared.';
    };
    document.getElementById('restart').onclick = function () {
        var service = serviceSelect.value;
        if (!service) { showError('Choose a service first.'); return; }
        var confirmation = window.prompt('Type RESTART to confirm restarting ' + service);
        if (confirmation === 'RESTART') run('restart_service', service, confirmation);
    };
    var buttons = document.querySelectorAll('[data-action]');
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].onclick = (function (button) {
            return function () { run(button.getAttribute('data-action'), null, null); };
        }(buttons[i]));
    }
    token.value = savedToken();
    token.onchange = function () { saveToken(token.value); };
    if (token.value) connect();
}());
