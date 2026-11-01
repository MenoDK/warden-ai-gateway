/* Content for the landing page and the lab. Everything the page says about behaviour is backed by a test
   (see tests/test_transcripts.py); the output in the tour is recorded from the running service. */
window.SITE = {
  name: 'warden-ai-gateway',
  short: 'Warden',
  title: 'warden-ai-gateway · an AI gateway that knows when to say no',
  logo: 'shield',
  repo: 'https://github.com/MenoDK/warden-ai-gateway',
  accent: {
    light: { fill: '#2fb98a', ink: '#0b6b4b', on: '#05231a', soft: '#dff4ea', onNavy: '#5fd8a7' },
    dark: { fill: '#4cc9a0', ink: '#7fe0bd', on: '#052016', soft: '#12342a', onNavy: '#5fd8a7' },
  },
  loading: {
    context: 'AI gateway',
    title: 'Waking the warden',
    text: 'Checking providers, circuit breakers and the evidence policy.',
    icon: 'shield',
    satellites: ['lock', 'search', 'check'],
    foot: 'Local demo · nothing leaves this machine',
    sketch: 'M12 120C60 40 100 150 168 78S290 24 330 96',
  },
  lab: { href: 'lab.html', cta: 'Enter the lab', signin: 'Sign in' },
  auth: { header: 'x-api-key' },

  hero: {
    eyebrow: 'AI gateway · fail-closed by design',
    lead: 'An AI gateway',
    soft: 'that knows when to say no.',
    text: 'Put language models behind rules. Requests are routed by what they contain, knowledge enters the index only after a person approves it, and every webhook is signed, timestamped and counted once.',
    primary: { label: 'Open the lab', href: 'lab.html' },
    secondary: { label: 'See how it works', href: '#tour', icon: 'layers' },
    pilot: 'Runs on your laptop · no API keys, no cloud account',
    proof: [
      { icon: 'lock', a: 'Sensitive data stays', b: 'inside the boundary' },
      { icon: 'flask', a: 'Every rule has a test', b: 'that tries to break it' },
    ],
    top: ['WARDEN', 'Nothing crosses unless the rules say so.'],
    status: { icon: 'shield', small: 'Last request', strong: 'Sensitive → local only. The cloud never saw it.' },
    art: `<svg viewBox="0 50 500 620" role="img" aria-label="A robot guard standing in a gate: a message with personal data is turned back from the cloud, a masked one is let through.">
      <g class="a-line"><path d="M0 120H500M0 240H500M0 360H500M0 480H500M0 600H500M100 30V700M250 30V700M400 30V700"/></g>
      <circle cx="250" cy="300" r="190" class="a-soft"/>
      <g transform="translate(250 300) scale(.9) translate(-250 -300)">
      <rect x="186" y="132" width="128" height="14" rx="7" class="a-body"/>
      <rect x="186" y="146" width="14" height="330" rx="6" class="a-body"/>
      <rect x="300" y="146" width="14" height="330" rx="6" class="a-body"/>
      <text x="250" y="116" text-anchor="middle" class="a-text">TRUST BOUNDARY</text>
      <path d="M250 150V470" class="a-dash"/>
      <g>
        <line x1="250" y1="186" x2="250" y2="166" class="a-accent-s"/>
        <circle cx="250" cy="160" r="6" class="a-accent pulse"/>
        <rect x="214" y="186" width="72" height="62" rx="16" class="a-body"/>
        <rect x="226" y="208" width="48" height="15" rx="7.5" class="a-accent"/>
        <rect x="204" y="262" width="92" height="104" rx="20" class="a-body"/>
        <path d="M250 280l22 8v14c0 14-9 24-22 29-13-5-22-15-22-29v-14l22-8z" class="a-accent-s"/>
        <path d="M241 304l7 7 12-13" class="a-accent-s"/>
        <rect x="182" y="272" width="16" height="64" rx="8" class="a-body"/>
        <rect x="302" y="272" width="16" height="64" rx="8" class="a-body"/>
        <rect x="222" y="372" width="20" height="44" rx="8" class="a-body"/>
        <rect x="258" y="372" width="20" height="44" rx="8" class="a-body"/>
      </g>
      <g>
        <rect x="26" y="236" width="104" height="48" rx="12" class="a-body"/>
        <path d="M42 252h52M42 266h34" class="a-line"/>
        <circle cx="112" cy="252" r="5" class="a-bad-f"/>
        <text x="26" y="228" class="a-text-s">prompt + e-mail</text>
        <rect x="26" y="326" width="104" height="48" rx="12" class="a-body"/>
        <path d="M42 342h52M42 356h28" class="a-line"/>
        <text x="26" y="318" class="a-text-s">plain question</text>
        <g class="travel"><rect x="132" y="253" width="18" height="12" rx="3" class="a-accent"/></g>
        <g class="travel b"><rect x="132" y="343" width="18" height="12" rx="3" class="a-accent"/></g>
      </g>
      <g>
        <rect x="204" y="440" width="92" height="46" rx="12" class="a-body"/>
        <circle cx="222" cy="463" r="4" class="a-accent"/><path d="M236 463h44" class="a-line"/>
        <text x="250" y="510" text-anchor="middle" class="a-text">LOCAL MODEL</text>
        <path d="M250 366V436" class="a-accent-s"/>
      </g>
      <g>
        <path d="M368 300a22 22 0 0 1 4-43 30 30 0 0 1 58-6 24 24 0 0 1 6 49z" class="a-body"/>
        <text x="400" y="336" text-anchor="middle" class="a-text">CLOUD</text>
        <text x="372" y="244" class="a-text-s">&lt;EMAIL_1&gt;</text>
        <path d="M318 286H356" class="a-dash"/>
        <path d="M326 276l16 20M342 276l-16 20" class="a-bad"/>
      </g>
      </g>
    </svg>`,
  },

  principles: {
    lead: ['Built to be', 'questioned.'],
    items: [
      ['lock', 'Fails closed'],
      ['search', 'Cites its sources'],
      ['users', 'Humans approve'],
      ['flask', 'Proven by tests'],
    ],
  },

  tour: {
    eyebrow: 'A tour of the whole thing',
    title: ['Four ways it says no,', 'and one way it says yes.'],
    text: 'Pick a tab. The output below is recorded from the running service with fictional data; a test fails if it ever stops being true.',
    tag: 'Recorded output',
    tabs: [
      {
        id: 'routing',
        label: 'Routing',
        icon: 'route',
        title: 'The content decides where it can go.',
        text: 'Personal data and secrets are detected and pinned to local models. Anything else may leave, but only pseudonymised.',
        lab: 'lab.html#gateway',
        transcript: (window.TRANSCRIPTS || {}).routing || '',
      },
      {
        id: 'outage',
        label: 'Outage',
        icon: 'bolt',
        title: 'When the safe path is down, it fails instead of leaking.',
        text: 'Sensitive text gets a 503, not a cloud model. Internal text may use the cloud, and the cloud inbox proves it received placeholders.',
        lab: 'lab.html#gateway',
        transcript: (window.TRANSCRIPTS || {}).outage || '',
      },
      {
        id: 'knowledge',
        label: 'Knowledge',
        icon: 'book',
        title: 'A document is data until a person says otherwise.',
        text: 'The hidden instruction is cut out as a whole chunk, the document waits for a curator, and answers carry exact source offsets.',
        lab: 'lab.html#knowledge',
        transcript: (window.TRANSCRIPTS || {}).knowledge || '',
      },
      {
        id: 'webhooks',
        label: 'Webhooks',
        icon: 'key',
        title: 'Tampering and replay get the same blank wall.',
        text: 'The signature covers the timestamp and the body, the event id is claimed atomically, and every failure returns one generic 401.',
        lab: 'lab.html#webhooks',
        transcript: (window.TRANSCRIPTS || {}).webhook || '',
      },
    ],
    modulesTitle: 'Everything in the box.',
    modulesNote: 'Each one has a test file and a place in the lab',
    modules: [
      ['route', 'Sensitivity routing', 'Personal data and secrets stay on local models. The rest may leave, pseudonymised, and is re-hydrated on the way back.'],
      ['bolt', 'Circuit breakers', 'One per provider. An open breaker is skipped instead of waited on, and a single probe tests recovery.'],
      ['book', 'Quarantine-first RAG', 'Documents wait for a curator. Chunks that try to instruct the model are excluded whole; their offsets, not their text, are kept.'],
      ['search', 'Evidence policy', 'A similarity threshold and a minimum evidence count gate the model. “Not enough evidence” is a normal, cheap answer.'],
      ['users', 'Human in the loop', 'A LangGraph workflow pauses before release, checkpointed, so a person approves, edits or rejects the draft.'],
      ['key', 'Signed webhooks', 'HMAC over timestamp and body, a replay window, atomic de-duplication and secrets that rotate without downtime.'],
    ],
    transparency: {
      strong: 'Honest about the demo.',
      text: 'The two “models” here are deterministic stand-ins and the embedder is lexical, so the lab shows the plumbing and the rules, not the quality of an answer. Point LOCAL_LLM_URL at Ollama, or any OpenAI-compatible server, and nothing else changes.',
    },
  },

  challenges: {
    eyebrow: 'The hard parts',
    title: ['Go on,', 'try to break it.'],
    text: 'These are the five things that are easy to claim and hard to get right. Each one has a recipe, what you should see, and a button that opens the lab on that exact tab.',
    items: [
      {
        label: 'Make it leak',
        icon: 'lock',
        access: 'Lab · Gateway',
        title: 'Try to get personal data to the cloud.',
        text: 'Switch the safe path off and see whether pressure changes the policy.',
        steps: [
          'Open the <code>Gateway</code> tab and switch <code>demo-local</code> off.',
          'Send the “contains an e-mail” sample with sensitivity on <code>auto</code>.',
          'Send it again with sensitivity set to <code>internal</code>, then open the cloud inbox.',
        ],
        expect: 'The first request is refused with 503 and the inbox stays empty. The second reaches the cloud, but the inbox shows <EMAIL_1>, never the address.',
        lab: 'lab.html#gateway',
      },
      {
        label: 'Poison the index',
        icon: 'alert',
        access: 'Lab · Knowledge',
        title: 'Hide an instruction inside a document.',
        text: 'Retrieval-time attacks start at ingestion. See where this one stops.',
        steps: [
          'In <code>Knowledge</code>, load the “poisoned handbook” sample and ingest it.',
          'Ask a question before approving: the policy answers without calling a model.',
          'Approve the document and ask again.',
        ],
        expect: 'Status <code>quarantined</code>, one chunk flagged by offset only. After approval the benign chunk answers with a citation; the poisoned one never becomes retrievable.',
        lab: 'lab.html#knowledge',
      },
      {
        label: 'Replay a webhook',
        icon: 'refresh',
        access: 'Lab · Webhooks',
        title: 'Send the same signed event twice, then tamper.',
        text: 'Signatures stop forgery; replay and tampering need more than that.',
        steps: [
          'In <code>Webhooks</code>, press “Send valid”.',
          'Press “Send again” (same event id), then “Tamper with the body”, then “Back-date the timestamp”.',
          'Compare the three failures.',
        ],
        expect: 'accepted, then duplicate, then two identical 401 answers. The reason is only in the metrics, never in the response.',
        lab: 'lab.html#webhooks',
      },
      {
        label: 'Break the breaker',
        icon: 'bolt',
        access: 'Lab · Gateway',
        title: 'Keep failing until a provider is cut off.',
        text: 'A breaker is only believable once you have watched it open.',
        steps: [
          'Switch both providers off in the <code>Gateway</code> tab.',
          'Send three requests: each fails and counts against its provider.',
          'Send a fourth, then switch the providers back on and press “Reset breakers”.',
        ],
        expect: 'After three failures both breakers read open and the fourth trace says circuit_open without a call being made. Reset restores service.',
        lab: 'lab.html#gateway',
      },
      {
        label: 'Pause for a human',
        icon: 'users',
        access: 'Lab · Review',
        title: 'Start an answer that nobody has released yet.',
        text: 'Some answers should not leave until someone has read them.',
        steps: [
          'Ingest and approve a document first (the Knowledge tab has a one-click sample).',
          'In <code>Review</code>, ask a question that contains an e-mail address.',
          'Edit the draft and approve it, or reject it.',
        ],
        expect: 'The run waits in <code>awaiting_review</code>. The stored question already has the address masked, and only your decision releases text.',
        lab: 'lab.html#review',
      },
    ],
  },

  run: {
    eyebrow: 'Run it in a minute',
    title: ['One command.', 'Everything on localhost.'],
    text: 'You need Docker. There are no API keys, no accounts to create and nothing leaves your machine.',
    steps: [
      ['terminal', 'Clone', 'git clone, then cd into the folder.'],
      ['play', 'Start', 'make demo builds the image and starts the API with PostgreSQL (pgvector) and Redis, health-gated.'],
      ['globe', 'Open', 'http://localhost:8000 is this page. Press “Enter the lab”.'],
      ['flask', 'Break it', 'Use the hard parts above, or run make check for the test suite.'],
    ],
    terminal: {
      title: 'bash',
      lines: [
        '# 1. get the code',
        'git clone https://github.com/MenoDK/warden-ai-gateway.git',
        'cd warden-ai-gateway',
        '# 2. start the API, PostgreSQL with pgvector, and Redis',
        'make demo',
        '# 3. open http://localhost:8000 and press “Enter the lab”',
        '# optional: the whole test suite (needs make install first)',
        'make check',
      ],
    },
  },

  under: {
    eyebrow: 'Under the hood',
    title: ['A small surface,', 'serious edges.'],
    text: 'The interesting code is short on purpose. The decisions behind it are written down with the alternatives that lost.',
    stackTitle: 'What it is built with',
    stack: [
      { group: 'Service', items: ['Python 3.11+', 'FastAPI', 'Pydantic v2', 'httpx'] },
      { group: 'AI', items: ['LangGraph (interrupt + checkpoints)', 'pgvector · HNSW', 'Embedder port', 'OpenAI-compatible providers · Ollama'] },
      { group: 'Data', items: ['PostgreSQL 16', 'Redis 7'] },
      { group: 'Quality', items: ['pytest', 'ruff', 'mypy --strict', 'GitHub Actions'] },
      { group: 'Delivery', items: ['Multi-stage Dockerfile, non-root', 'Compose, health-gated', 'Prometheus metrics'] },
    ],
    proofTitle: 'What is measured, and the records behind it',
    numbers: [
      ['164', 'unit and API tests'],
      ['2', 'integration tests on real PostgreSQL and Redis'],
      ['5', 'decision records, each with rejected alternatives'],
      ['0', 'errors under mypy --strict'],
    ],
    decisions: [
      ['Fail closed on sensitive data', 'ADR 0001: why there is no “fall back to the cloud”.', 'docs/adr/0001-fail-closed-sensitivity-routing.md'],
      ['Quarantine by default', 'ADR 0002: documents are data, never orders.', 'docs/adr/0002-quarantine-by-default-rag.md'],
      ['A partial index for approved chunks', 'ADR 0003: why a join after the ANN search returns too few rows.', 'docs/adr/0003-partial-hnsw-index.md'],
      ['Signed, deduplicated webhooks', 'ADR 0004: replay, tampering and the generic 401.', 'docs/adr/0004-signed-timestamped-deduplicated-webhooks.md'],
    ],
    measuredOn: 'Measured on 2026-11-01. Counts come from the commands in the README, not from memory.',
    future: [
      ['A semantic embedder', 'behind the existing Embedder port (today it is lexical).'],
      ['Durable review checkpoints', 'on PostgreSQL instead of in memory.'],
      ['A worker', 'for webhook handlers that stop being fast.'],
    ],
  },

  about: {
    why: 'Warden is the AI side of my work: applied AI where a mistake has a cost. The ideas come from systems I have built and operated; the code in this repository is written fresh and tested.',
  },

  faq: [
    ['Is there a real sign-up?', 'No, on purpose. This service uses one API key (see the limitations in the README); accounts and tenants live in bulkhead-saas. The lab still shows the same sign-in screen and fills in the development key for you.'],
    ['Is it talking to a real language model?', 'By default no: two deterministic stand-ins run, so every rule is testable and the demo works offline. Set LOCAL_LLM_URL to Ollama or any OpenAI-compatible server for a real one.'],
    ['Can the lab mode reach production?', 'No. The settings validator refuses LAB_MODE when APP_ENV is production, and a test pins that. The outage switches and the cloud inbox do not exist outside it.'],
    ['Why quarantine instead of filtering at query time?', 'Because every caller would have to remember the filter. The store enforces that retrieval only sees approved documents, so a caller cannot forget it. ADR 0002 has the rejected alternatives.'],
    ['Is it production-ready?', 'It is built and tested to that standard: strict types, real-database tests, adversarial cases. It has not carried real traffic, and what it lacks is listed under “Not built yet” and in the README limitations.'],
  ],

  closing: {
    eyebrow: 'Your turn',
    title: ['Try to make it say yes', 'when it should say no.'],
    button: 'Open the lab',
    fine: 'Local only · fictional data · nothing is sent anywhere',
  },
};
