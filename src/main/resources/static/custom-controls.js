(() => {
  let openControl = null;
  const monthFormat = new Intl.DateTimeFormat('en-US', {month:'long', year:'numeric'});
  const dateFormat = new Intl.DateTimeFormat('en-US', {weekday:'short', month:'short', day:'numeric', hour:'numeric', minute:'2-digit'});
  const pad = number => String(number).padStart(2, '0');

  function closeOpen() {
    if (!openControl) return;
    openControl.panel.hidden = true;
    openControl.trigger.setAttribute('aria-expanded', 'false');
    openControl = null;
  }
  function positionPanel(control) {
    control.host.classList.remove('opens-up');
    const rect = control.host.getBoundingClientRect();
    const height = control.panel.getBoundingClientRect().height;
    if (rect.bottom + height + 12 > window.innerHeight && rect.top > height + 18)
      control.host.classList.add('opens-up');
  }
  function open(control) {
    if (openControl === control) { closeOpen(); return; }
    closeOpen();
    control.panel.hidden = false;
    control.trigger.setAttribute('aria-expanded', 'true');
    openControl = control;
    positionPanel(control);
  }
  function wrap(input, type) {
    const host = document.createElement('div');
    host.className = 'enhanced-control ' + type;
    input.before(host);
    host.append(input);
    input.classList.add('native-control');
    input.tabIndex = -1;
    input.setAttribute('aria-hidden', 'true');
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'control-trigger';
    trigger.setAttribute('aria-haspopup', type === 'date-control' ? 'dialog' : 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    host.append(trigger);
    const panel = document.createElement('div');
    panel.className = 'control-panel';
    panel.hidden = true;
    host.append(panel);
    return {host, trigger, panel, input};
  }
  function optionButtons(control, filter = '') {
    const list = control.panel.querySelector('.choice-list');
    list.replaceChildren();
    const options = [...control.input.options].filter(option => !filter || option.textContent.toLowerCase().includes(filter.toLowerCase()));
    options.forEach(option => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'choice-option' + (option.value === control.input.value ? ' selected' : '');
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(option.value === control.input.value));
      button.dataset.value = option.value;
      button.textContent = option.textContent;
      button.disabled = option.disabled;
      button.addEventListener('click', () => {
        control.input.value = option.value;
        control.input.dispatchEvent(new Event('change', {bubbles:true}));
        closeOpen();
        control.trigger.focus();
      });
      list.append(button);
    });
    if (!options.length) {
      const empty = document.createElement('span');
      empty.className = 'choice-empty';
      empty.textContent = 'No matching places';
      list.append(empty);
    }
  }
  function enhanceSelect(input) {
    if (input.closest('.enhanced-control')) return;
    const control = wrap(input, 'choice-control');
    const label = input.getAttribute('aria-label') || input.closest('label')?.querySelector('span')?.textContent || 'Choose an option';
    control.trigger.setAttribute('aria-label', label);
    control.trigger.innerHTML = '<span class="control-value"></span><span class="control-chevron" aria-hidden="true"></span>';
    const list = document.createElement('div');
    list.className = 'choice-list';
    list.setAttribute('role', 'listbox');
    control.panel.append(list);
    if (input.options.length > 10) {
      const search = document.createElement('input');
      search.type = 'search';
      search.className = 'choice-search';
      search.placeholder = /opens|closes/i.test(label) ? 'Find a time'
        : input.id === 'actor' ? 'Find a profile'
        : input.id === 'place-filter' ? 'Find a place' : 'Search options';
      search.setAttribute('aria-label', 'Search options');
      search.addEventListener('input', () => optionButtons(control, search.value));
      control.panel.prepend(search);
    }
    control.sync = () => {
      control.trigger.querySelector('.control-value').textContent = input.selectedOptions[0]?.textContent || 'Choose';
      if (!control.panel.hidden) optionButtons(control, control.panel.querySelector('.choice-search')?.value || '');
    };
    input.addEventListener('change', control.sync);
    new MutationObserver(control.sync).observe(input, {childList:true, subtree:true, attributes:true, attributeFilter:['selected']});
    control.trigger.addEventListener('click', () => {
      optionButtons(control);
      const search = control.panel.querySelector('.choice-search');
      if (search) search.value = '';
      open(control);
      if (!control.panel.hidden) (search || control.panel.querySelector('.choice-option.selected'))?.focus();
    });
    control.host.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeOpen(); control.trigger.focus(); return; }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (control.panel.hidden) { optionButtons(control); open(control); }
        const options = [...control.panel.querySelectorAll('.choice-option:not(:disabled)')];
        const index = options.indexOf(document.activeElement);
        options[(index + (event.key === 'ArrowDown' ? 1 : options.length - 1)) % options.length]?.focus();
      }
      if (event.key === 'Enter' && document.activeElement.classList.contains('choice-option')) {
        event.preventDefault(); document.activeElement.click();
      }
    });
    input._customControl = control;
    control.sync();
  }

  function enhanceDate(input) {
    if (input.closest('.enhanced-control')) return;
    const control = wrap(input, 'date-control');
    control.panel.setAttribute('role', 'dialog');
    control.panel.setAttribute('aria-label', 'Choose date and time');
    control.trigger.setAttribute('aria-label', input.closest('label')?.textContent.trim() || 'Choose date and time');
    control.trigger.innerHTML = '<span class="control-value"></span><span class="date-glyph" aria-hidden="true"></span>';
    control.panel.innerHTML = '<div class="calendar-head"><button type="button" data-month="-1" aria-label="Previous month">‹</button><strong></strong><button type="button" data-month="1" aria-label="Next month">›</button></div><div class="calendar-weekdays"><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span><span>Su</span></div><div class="calendar-days"></div><div class="calendar-time"><span>Time</span><label><input type="number" min="0" max="23" aria-label="Hour"> h</label><label><input type="number" min="0" max="59" step="15" aria-label="Minute"> min</label></div><button type="button" class="calendar-apply">Apply date and time</button>';
    const today = new Date();
    control.year = today.getFullYear(); control.month = today.getMonth();
    const hours = control.panel.querySelector('[aria-label="Hour"]');
    const minutes = control.panel.querySelector('[aria-label="Minute"]');
    const selected = () => input.value ? new Date(input.value) : new Date();
    function setValue(day, hour, minute) {
      const value = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, minute);
      input.value = `${value.getFullYear()}-${pad(value.getMonth()+1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
      input.dispatchEvent(new Event('change', {bubbles:true}));
      control.sync();
    }
    control.renderDays = () => {
      control.panel.querySelector('.calendar-head strong').textContent = monthFormat.format(new Date(control.year, control.month, 1));
      const days = control.panel.querySelector('.calendar-days');
      days.replaceChildren();
      const offset = (new Date(control.year, control.month, 1).getDay() + 6) % 7;
      const count = new Date(control.year, control.month + 1, 0).getDate();
      for (let i = 0; i < offset; i++) days.append(document.createElement('span'));
      const current = selected();
      for (let day = 1; day <= count; day++) {
        const button = document.createElement('button');
        button.type = 'button'; button.textContent = day;
        button.className = 'calendar-day';
        if (current.getFullYear() === control.year && current.getMonth() === control.month && current.getDate() === day)
          button.classList.add('selected');
        if (new Date(control.year, control.month, day + 1) <= new Date()) button.disabled = true;
        button.addEventListener('click', () => {
          setValue(new Date(control.year, control.month, day), Number(hours.value), Number(minutes.value));
          control.renderDays();
        });
        days.append(button);
      }
    };
    control.sync = () => {
      const value = input.value ? new Date(input.value) : null;
      control.trigger.querySelector('.control-value').textContent = value && !Number.isNaN(+value)
        ? dateFormat.format(value) : 'Choose date and time';
    };
    control.trigger.addEventListener('click', () => {
      const value = selected();
      control.year = value.getFullYear(); control.month = value.getMonth();
      hours.value = pad(value.getHours()); minutes.value = pad(value.getMinutes());
      control.renderDays(); open(control);
    });
    control.panel.querySelectorAll('[data-month]').forEach(button => button.addEventListener('click', () => {
      const date = new Date(control.year, control.month + Number(button.dataset.month), 1);
      control.year = date.getFullYear(); control.month = date.getMonth(); control.renderDays(); positionPanel(control);
    }));
    [hours, minutes].forEach(field => field.addEventListener('change', () => {
      const value = selected();
      const hour = Math.max(0, Math.min(23, Number(hours.value) || 0));
      const minute = Math.max(0, Math.min(59, Number(minutes.value) || 0));
      hours.value = pad(hour); minutes.value = pad(minute);
      setValue(value, hour, minute);
    }));
    control.panel.querySelector('.calendar-apply').addEventListener('click', () => { closeOpen(); control.trigger.focus(); });
    control.host.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault(); event.stopPropagation(); closeOpen(); control.trigger.focus();
      }
    });
    input.addEventListener('change', control.sync);
    input._customControl = control;
    control.sync();
  }
  function enhanceAll() {
    document.querySelectorAll('select:not(.native-control)').forEach(enhanceSelect);
    document.querySelectorAll('input[type="datetime-local"]:not(.native-control)').forEach(enhanceDate);
  }
  function refresh() {
    enhanceAll();
    document.querySelectorAll('.native-control').forEach(input => input._customControl?.sync());
  }
  let scheduled = false;
  new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; enhanceAll(); });
  }).observe(document.body, {childList:true, subtree:true});
  document.addEventListener('pointerdown', event => {
    if (openControl && !openControl.host.contains(event.target)) closeOpen();
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeOpen(); });
  window.refreshCustomControls = refresh;
  refresh();
})();
