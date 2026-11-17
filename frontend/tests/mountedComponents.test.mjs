import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import React, { act, useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Routes, Route, Outlet } from 'react-router-dom';

import {
  rowsToEditable,
  updateRowYearText,
  removeRow,
  moveRow,
  editableToCanonical,
  hasRowValidationErrors
} from '../.jdrows-test/jdRows.js';

function setupDOM() {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'http://localhost:3000/',
    pretendToBeVisual: true
  });
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  try {
    Object.defineProperty(globalThis, 'navigator', {
      value: dom.window.navigator,
      configurable: true,
      writable: true
    });
  } catch {
    // navigator getter exists
  }
  globalThis.Element = dom.window.Element;
  globalThis.HTMLElement = dom.window.HTMLElement;
  globalThis.HTMLInputElement = dom.window.HTMLInputElement;
  globalThis.HTMLTextAreaElement = dom.window.HTMLTextAreaElement;
  globalThis.HTMLButtonElement = dom.window.HTMLButtonElement;
  globalThis.HTMLSelectElement = dom.window.HTMLSelectElement;
  globalThis.Event = dom.window.Event;
  globalThis.MouseEvent = dom.window.MouseEvent;
  globalThis.localStorage = dom.window.localStorage;
  globalThis.sessionStorage = dom.window.sessionStorage;
  if (!dom.window.matchMedia) {
    dom.window.matchMedia = () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} });
  }
  globalThis.EventSource = class MockEventSource {
    constructor() {}
    addEventListener() {}
    removeEventListener() {}
    close() {}
  };
  return { dom, window: dom.window, document: dom.window.document, Event: dom.window.Event };
}

test('Mounted: 1. JD editing and row identity preservation in mounted DOM', async () => {
  const { document } = setupDOM();
  const container = document.getElementById('root');
  const root = createRoot(container);

  function JDEditorHarness({ initialRows, onSave }) {
    const [rows, setRows] = useState(() => rowsToEditable(initialRows));
    const [dirty, setDirty] = useState(false);

    return React.createElement('div', { id: 'jd-editor' },
      React.createElement('div', { id: 'dirty-flag' }, dirty ? 'DIRTY' : 'CLEAN'),
      rows.map((row, index) =>
        React.createElement('div', { key: row._clientKey, className: 'row-item', 'data-clientkey': row._clientKey },
          React.createElement('span', { className: 'req-id' }, row.ID || 'NEW'),
          React.createElement('input', {
            className: 'min-years-input',
            'data-testid': `years-${row._clientKey}`,
            value: row.yearText,
            onChange: e => {
              setDirty(true);
              setRows(r => updateRowYearText(r, row._clientKey, e.target.value));
            }
          }),
          row.yearError ? React.createElement('span', { className: 'year-error' }, row.yearError) : null,
          React.createElement('button', {
            className: 'btn-delete',
            'data-testid': `del-${row._clientKey}`,
            onClick: () => {
              setDirty(true);
              setRows(r => removeRow(r, row._clientKey));
            }
          }, 'Delete'),
          React.createElement('button', {
            className: 'btn-up',
            'data-testid': `up-${row._clientKey}`,
            disabled: index === 0,
            onClick: () => {
              setDirty(true);
              setRows(r => moveRow(r, index, index - 1));
            }
          }, 'Up')
        )
      ),
      React.createElement('button', {
        id: 'btn-save',
        onClick: () => {
          if (!hasRowValidationErrors(rows)) {
            onSave(editableToCanonical(rows));
          }
        }
      }, 'Save')
    );
  }

  let savedPayload = null;
  const initial = [
    { ID: 'R001', Requirement: 'Python', Priority: 'required', Type: 'skill', 'JD source': 'Py', 'Minimum years': 3 },
    { ID: 'R002', Requirement: 'Architecture', Priority: 'required', Type: 'skill', 'JD source': 'Arch', 'Minimum years': 7 }
  ];

  await act(async () => {
    root.render(React.createElement(JDEditorHarness, {
      initialRows: initial,
      onSave: p => { savedPayload = p; }
    }));
  });

  const rowElsBefore = container.querySelectorAll('.row-item');
  assert.equal(rowElsBefore.length, 2);
  const input0 = container.querySelector('[data-testid="years-' + rowElsBefore[0].dataset.clientkey + '"]');
  const input1 = container.querySelector('[data-testid="years-' + rowElsBefore[1].dataset.clientkey + '"]');
  assert.equal(input0.value, '3');
  assert.equal(input1.value, '7');

  // Delete R001
  const del0 = container.querySelector('[data-testid="del-' + rowElsBefore[0].dataset.clientkey + '"]');
  await act(async () => {
    del0.click();
  });

  // Verify that only 1 row remains and its value is strictly 7, NOT 3!
  const rowElsAfter = container.querySelectorAll('.row-item');
  assert.equal(rowElsAfter.length, 1);
  const remainingInput = rowElsAfter[0].querySelector('.min-years-input');
  assert.equal(remainingInput.value, '7');

  // Save and inspect canonical payload
  const saveBtn = container.querySelector('#btn-save');
  await act(async () => {
    saveBtn.click();
  });

  assert.equal(savedPayload.length, 1);
  assert.equal(savedPayload[0].ID, 'R002');
  assert.equal(savedPayload[0]['Minimum years'], 7);
  assert.equal(savedPayload[0]._clientKey, undefined);
  root.unmount();
});

test('Mounted: 2. Pagination recovery on revision conflict with working refresh action', async () => {
  const { document } = setupDOM();
  const container = document.getElementById('root');
  const root = createRoot(container);

  function RankingsHarness({ fetchPage }) {
    const [page, setPage] = useState(0);
    const [rows, setRows] = useState([]);
    const [error, setError] = useState(null);
    const [revision, setRevision] = useState(1);
    const pinned = useRef(null);

    const loadPage = async (targetPage, forceReset = false) => {
      if (forceReset || targetPage === 0) pinned.current = null;
      try {
        const res = await fetchPage(targetPage, pinned.current);
        if (pinned.current && targetPage > 0 && res.revision !== pinned.current) {
          pinned.current = null;
          throw new Error('Ranking changed while browsing. Return to page one.');
        }
        if (targetPage === 0 || !pinned.current) pinned.current = res.revision;
        setRows(res.items);
        setRevision(res.revision);
        setPage(targetPage);
        setError(null);
      } catch (err) {
        setRows([]);
        setError(err.message);
      }
    };

    useEffect(() => {
      void loadPage(0);
    }, []);

    return React.createElement('div', { id: 'rankings' },
      error ? React.createElement('div', { id: 'error-banner' },
        React.createElement('span', { id: 'error-msg' }, error),
        React.createElement('button', {
          id: 'btn-refresh',
          onClick: () => void loadPage(0, true)
        }, 'Refresh rankings')
      ) : null,
      React.createElement('div', { id: 'page-info' }, `Page ${page} Rev ${revision} Count ${rows.length}`),
      rows.map(r => React.createElement('div', { key: r.id, className: 'candidate-row' }, r.name)),
      React.createElement('button', {
        id: 'btn-next',
        onClick: () => void loadPage(page + 1)
      }, 'Next page')
    );
  }

  let serverRevision = 1;
  const mockFetch = async (pageIndex, pinnedRev) => {
    if (pinnedRev && pageIndex > 0 && pinnedRev !== serverRevision) {
      throw new Error('Ranking revision conflict');
    }
    return {
      revision: serverRevision,
      items: Array.from({ length: 5 }, (_, i) => ({
        id: `p${pageIndex}-c${i}`,
        name: `Candidate ${pageIndex * 5 + i} (rev ${serverRevision})`
      }))
    };
  };

  await act(async () => {
    root.render(React.createElement(RankingsHarness, { fetchPage: mockFetch }));
  });

  assert.equal(container.querySelector('#page-info').textContent, 'Page 0 Rev 1 Count 5');
  assert.equal(container.querySelectorAll('.candidate-row').length, 5);

  // Now server revision changes from another tab/action
  serverRevision = 2;

  // Attempt to go to page 2 (index 1)
  const nextBtn = container.querySelector('#btn-next');
  await act(async () => {
    nextBtn.click();
  });

  // Revision conflict occurs! Stale data is cleared
  assert.ok(container.querySelector('#error-banner'));
  assert.equal(container.querySelectorAll('.candidate-row').length, 0);

  // Click refresh rankings action
  const refreshBtn = container.querySelector('#btn-refresh');
  await act(async () => {
    refreshBtn.click();
  });

  // Recovered successfully on page 0 with revision 2!
  assert.equal(container.querySelector('#error-banner'), null);
  assert.equal(container.querySelector('#page-info').textContent, 'Page 0 Rev 2 Count 5');
  assert.equal(container.querySelectorAll('.candidate-row').length, 5);
  root.unmount();
});

test('Mounted: 3. Progress resume dispatches action and restarts observation', async () => {
  const { document } = setupDOM();
  const container = document.getElementById('root');
  const root = createRoot(container);

  function ProgressHarness({ initialJob, onResume }) {
    const [job, setJob] = useState(initialJob);
    const [epoch, setEpoch] = useState(0);

    const handleResume = async () => {
      await onResume(job.id);
      setJob(j => ({ ...j, state: 'running' }));
      setEpoch(e => e + 1);
    };

    return React.createElement('div', { id: 'progress-view' },
      React.createElement('div', { id: 'job-state' }, job.state),
      React.createElement('div', { id: 'obs-epoch' }, `Epoch ${epoch}`),
      job.state === 'cancelled' || job.state === 'failed' || job.state === 'paused'
        ? React.createElement('button', {
            id: 'btn-resume',
            onClick: () => void handleResume()
          }, 'Resume eligible work')
        : null
    );
  }

  let resumedJobId = null;
  await act(async () => {
    root.render(React.createElement(ProgressHarness, {
      initialJob: { id: 'job-123', state: 'cancelled' },
      onResume: async jid => { resumedJobId = jid; }
    }));
  });

  assert.equal(container.querySelector('#job-state').textContent, 'cancelled');
  assert.equal(container.querySelector('#obs-epoch').textContent, 'Epoch 0');

  const resumeBtn = container.querySelector('#btn-resume');
  assert.ok(resumeBtn);

  await act(async () => {
    resumeBtn.click();
  });

  assert.equal(resumedJobId, 'job-123');
  assert.equal(container.querySelector('#job-state').textContent, 'running');
  assert.equal(container.querySelector('#obs-epoch').textContent, 'Epoch 1');
  assert.equal(container.querySelector('#btn-resume'), null);
  root.unmount();
});

test('Mounted: 4. Poll-only completion terminates gracefully without infinite polling', async () => {
  const { document } = setupDOM();
  const container = document.getElementById('root');
  const root = createRoot(container);

  function PollObservationHarness({ pollJob, onTerminal }) {
    const [state, setState] = useState('running');
    const [pollCount, setPollCount] = useState(0);
    const stoppedRef = useRef(false);

    useEffect(() => {
      let active = true;
      const interval = globalThis.setInterval(async () => {
        if (!active || stoppedRef.current) return;
        setPollCount(c => c + 1);
        const latest = await pollJob();
        setState(latest.state);
        if (latest.state === 'completed' || latest.state === 'failed') {
          stoppedRef.current = true;
          globalThis.clearInterval(interval);
          onTerminal(latest.state);
        }
      }, 50);

      return () => {
        active = false;
        globalThis.clearInterval(interval);
      };
    }, [pollJob, onTerminal]);

    return React.createElement('div', { id: 'poll-harness' },
      React.createElement('div', { id: 'poll-state' }, state),
      React.createElement('div', { id: 'poll-count' }, `Polls: ${pollCount}`)
    );
  }

  let polls = 0;
  let terminalState = null;
  const mockPoll = async () => {
    polls += 1;
    if (polls >= 3) {
      return { state: 'completed' };
    }
    return { state: 'running' };
  };

  await act(async () => {
    root.render(React.createElement(PollObservationHarness, {
      pollJob: mockPoll,
      onTerminal: s => { terminalState = s; }
    }));
  });

  // Wait for intervals
  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 250));
  });

  assert.equal(terminalState, 'completed');
  assert.equal(container.querySelector('#poll-state').textContent, 'completed');
  const finalPolls = polls;
  assert.ok(finalPolls >= 3);

  // Wait further and verify polling stopped completely
  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 150));
  });
  assert.equal(polls, finalPolls);
  root.unmount();
});

test('Mounted: 5. Dirty-edit preservation and server-conflict notification', async () => {
  const { document, window, Event } = setupDOM();
  const container = document.getElementById('root');
  const root = createRoot(container);

  function DirtyReviewHarness({ serverRevision, onSave }) {
    const [text, setText] = useState('Original JD Text');
    const [dirty, setDirty] = useState(false);
    const [editingRev] = useState(serverRevision);
    const isStale = dirty && editingRev !== serverRevision;

    useEffect(() => {
      const handler = e => {
        if (dirty) {
          e.preventDefault();
          e.returnValue = '';
        }
      };
      window.addEventListener('beforeunload', handler);
      return () => window.removeEventListener('beforeunload', handler);
    }, [dirty]);

    return React.createElement('div', { id: 'dirty-harness' },
      isStale ? React.createElement('div', { id: 'stale-warning' }, 'Newer revision published. Edits preserved.') : null,
      React.createElement('button', {
        id: 'btn-modify',
        onClick: () => {
          setDirty(true);
          setText('User modified text');
        }
      }, 'Modify'),
      React.createElement('textarea', {
        id: 'editor-text',
        value: text,
        readOnly: true
      }),
      React.createElement('button', {
        id: 'save-btn',
        disabled: isStale,
        onClick: () => {
          setDirty(false);
          onSave(text);
        }
      }, 'Save')
    );
  }

  let savedText = null;
  await act(async () => {
    root.render(React.createElement(DirtyReviewHarness, {
      serverRevision: 1,
      onSave: t => { savedText = t; }
    }));
  });

  const modifyBtn = container.querySelector('#btn-modify');
  await act(async () => {
    modifyBtn.click();
  });

  // Simulate beforeunload
  let prevented = false;
  await act(async () => {
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    prevented = event.defaultPrevented;
  });
  assert.equal(prevented, true);

  // Now server revision advances to 2 while user has unsaved edits
  await act(async () => {
    root.render(React.createElement(DirtyReviewHarness, {
      serverRevision: 2,
      onSave: t => { savedText = t; }
    }));
  });

  // Stale warning is rendered, save button is disabled, but user modified text is PRESERVED!
  assert.ok(container.querySelector('#stale-warning'));
  assert.equal(container.querySelector('#editor-text').value, 'User modified text');
  assert.equal(container.querySelector('#save-btn').disabled, true);
  assert.equal(savedText, null);
  root.unmount();
});

test('Mounted: 6. Route changes with in-flight requests ignore obsolete responses', async () => {
  const { document } = setupDOM();
  const container = document.getElementById('root');
  const root = createRoot(container);

  function RouteGenerationHarness({ activeRoute, fetchRouteData }) {
    const [data, setData] = useState(null);
    const generation = useRef(0);

    useEffect(() => {
      const currentGen = ++generation.current;
      setData(null);
      void fetchRouteData(activeRoute).then(result => {
        // Discard response if generation has advanced
        if (currentGen === generation.current) {
          setData(result);
        }
      });
    }, [activeRoute, fetchRouteData]);

    return React.createElement('div', { id: 'route-view' },
      React.createElement('div', { id: 'active-route' }, activeRoute),
      React.createElement('div', { id: 'route-data' }, data ? data.title : 'Loading...')
    );
  }

  const slowResolvers = {};
  const mockFetchRoute = route => new Promise(resolve => {
    slowResolvers[route] = resolve;
  });

  await act(async () => {
    root.render(React.createElement(RouteGenerationHarness, {
      activeRoute: '/route-A',
      fetchRouteData: mockFetchRoute
    }));
  });

  assert.equal(container.querySelector('#active-route').textContent, '/route-A');
  assert.equal(container.querySelector('#route-data').textContent, 'Loading...');

  // Rapidly navigate to route-B before route-A finishes
  await act(async () => {
    root.render(React.createElement(RouteGenerationHarness, {
      activeRoute: '/route-B',
      fetchRouteData: mockFetchRoute
    }));
  });

  assert.equal(container.querySelector('#active-route').textContent, '/route-B');

  // Now route-A's slow response finally arrives!
  await act(async () => {
    slowResolvers['/route-A']({ title: 'ROUTE A DATA (STALE)' });
  });

  // Route-B must NOT be corrupted by Route-A's stale response!
  assert.equal(container.querySelector('#route-data').textContent, 'Loading...');

  // Route-B response arrives
  await act(async () => {
    slowResolvers['/route-B']({ title: 'ROUTE B DATA (FRESH)' });
  });

  assert.equal(container.querySelector('#route-data').textContent, 'ROUTE B DATA (FRESH)');
  root.unmount();
});

test('Mounted Production: 7. Production JDPage mounted under real router with row identity and approval', async () => {
  const { document } = setupDOM();
  const { JDPage, client } = await import('../.test-dist/workflow/Workflow.js');

  let approvedPayload = null;
  client.getDraft = async () => ({
    id: 'draft-p7',
    revision: 1,
    document_id: 'doc-jd1',
    rows: [
      { ID: 'R001', Requirement: 'Python development', Priority: 'required', Type: 'skill', 'JD source': 'Must know Python', 'Minimum years': 3 },
      { ID: 'R002', Requirement: 'Cloud infrastructure', Priority: 'required', Type: 'skill', 'JD source': 'Must know Cloud', 'Minimum years': 7 }
    ]
  });
  client.approveJD = async (wsId, draftId, rev, rows) => {
    approvedPayload = rows;
    return { id: 'appr-1', draft_id: draftId, revision: rev + 1, body: { job_title: 'Engineer', requirements: [] } };
  };

  const container = document.getElementById('root');
  const root = createRoot(container);
  const mockContext = {
    workspaceId: 'ws-prod',
    data: {
      workspace: { id: 'ws-prod', name: 'Production WS' },
      documents: [{ id: 'doc-jd1', kind: 'jd', filename: 'job.txt' }],
      draft: {
        id: 'draft-p7',
        revision: 1,
        document_id: 'doc-jd1',
        body: {
          job_title: 'Engineer',
          requirements: [
            { requirement_id: 'R001', name: 'Python development', priority: 'required', experience_years: 3 },
            { requirement_id: 'R002', name: 'Cloud infrastructure', priority: 'required', experience_years: 7 }
          ],
          rows: [
            { ID: 'R001', Requirement: 'Python development', Priority: 'required', Type: 'skill', 'JD source': 'Must know Python', 'Minimum years': 3 },
            { ID: 'R002', Requirement: 'Cloud infrastructure', Priority: 'required', Type: 'skill', 'JD source': 'Must know Cloud', 'Minimum years': 7 }
          ]
        }
      },
      approved: null,
      weights: null,
      jobs: [],
      exports: [],
      history: []
    },
    settings: { configured_provider: 'ollama', yake_top_k_default: 15 },
    loading: false,
    error: null,
    refresh: async () => {}
  };

  await act(async () => {
    root.render(
      React.createElement(MemoryRouter, { initialEntries: ['/workspaces/ws-prod/jd'] },
        React.createElement(Routes, null,
          React.createElement(Route, { path: '/workspaces/:workspaceId', element: React.createElement(Outlet, { context: mockContext }) },
            React.createElement(Route, { path: 'jd', element: React.createElement(JDPage) })
          )
        )
      )
    );
  });

  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  const cards = container.querySelectorAll('.why');
  assert.equal(cards.length, 2);
  const yearInput0 = cards[0].querySelector('input[inputmode="decimal"]');
  const yearInput1 = cards[1].querySelector('input[inputmode="decimal"]');
  assert.equal(yearInput0.value, '3');
  assert.equal(yearInput1.value, '7');

  // Click Remove criterion on R001
  const removeBtn0 = cards[0].querySelector('button.btn.danger');
  await act(async () => {
    removeBtn0.click();
  });

  // Verify only 1 card remains and its value is strictly 7 (NOT 3!)
  const cardsAfter = container.querySelectorAll('.why');
  assert.equal(cardsAfter.length, 1);
  const remainingYearInput = cardsAfter[0].querySelector('input[inputmode="decimal"]');
  assert.equal(remainingYearInput.value, '7');
  assert.ok(cardsAfter[0].textContent.includes('R002'));

  // Click Approve and freeze JD
  const approveBtn = Array.from(container.querySelectorAll('button')).find(b => b.textContent.includes('Approve and freeze JD'));
  assert.ok(approveBtn);
  await act(async () => {
    approveBtn.click();
  });

  // Canonical payload verified: 1 row, ID R002, Minimum years 7, no client keys
  assert.ok(approvedPayload);
  assert.equal(approvedPayload.length, 1);
  assert.equal(approvedPayload[0].ID, 'R002');
  assert.equal(approvedPayload[0]['Minimum years'], 7);
  assert.equal(approvedPayload[0]._clientKey, undefined);
  root.unmount();
});

test('Mounted Production: 8. Production RankingsPage mounted with revision conflict and refresh recovery', async () => {
  const { document } = setupDOM();
  const { RankingsPage, client } = await import('../.test-dist/results/Results.js');

  let currentRevision = 1;
  client.getJob = async () => ({
    id: 'job-rank-p8',
    workspace_id: 'ws-prod',
    kind: 'assess',
    state: 'completed',
    progress: 100,
    total: 100,
    created: '2026-11-16T00:00:00Z',
    updated: '2026-11-16T00:00:00Z',
    message: 'Finished',
    request_json: '{}'
  });

  client.listRankings = async (_ws, _jid, options) => {
    const offset = options?.offset ?? 0;
    const expResult = options?.expectedResultRevision;
    if (offset > 0 && expResult && expResult !== currentRevision) {
      throw new Error('Ranking revision conflict: page revision does not match server revision');
    }
    return {
      resultRevision: currentRevision,
      weightRevision: currentRevision,
      total: 100,
      offset,
      limit: 50,
      officialCount: 100,
      unfinishedCount: 0,
      items: Array.from({ length: 50 }, (_, i) => ({
        candidate_index: offset + i,
        candidate_id: `cand-${offset + i}`,
        candidate: `Candidate ${offset + i}`,
        status: 'completed',
        primary_score: 90.0,
        weighted_score: 88.0,
        rank: offset + i + 1,
        evaluation_mode: 'fallback_exact'
      }))
    };
  };

  const container = document.getElementById('root');
  const root = createRoot(container);
  const mockContext = {
    workspaceId: 'ws-prod',
    data: {
      workspace: { id: 'ws-prod', name: 'Production WS' },
      documents: [],
      draft: null,
      approved: null,
      weights: null,
      jobs: [{ id: 'job-rank-p8', state: 'completed' }],
      exports: [],
      history: []
    },
    settings: { configured_provider: 'ollama' },
    loading: false,
    error: null,
    refresh: async () => {}
  };

  await act(async () => {
    root.render(
      React.createElement(MemoryRouter, { initialEntries: ['/workspaces/ws-prod/rankings/job-rank-p8'] },
        React.createElement(Routes, null,
          React.createElement(Route, { path: '/workspaces/:workspaceId', element: React.createElement(Outlet, { context: mockContext }) },
            React.createElement(Route, { path: 'rankings/:jobId', element: React.createElement(RankingsPage) })
          )
        )
      )
    );
  });

  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  assert.equal(container.querySelectorAll('tbody tr').length, 50);

  // Revision moves on server
  currentRevision = 2;

  // Navigate to next page
  const nextBtn = Array.from(container.querySelectorAll('button')).find(b => b.textContent.includes('Next page'));
  assert.ok(nextBtn);
  await act(async () => {
    nextBtn.click();
  });
  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  // Stale data cleared and error banner displayed with Refresh button
  const errorPanel = container.querySelector('.error-panel');
  assert.ok(errorPanel);
  assert.ok(errorPanel.textContent.includes('Revision notice'));
  assert.equal(container.querySelectorAll('tbody tr').length, 0);

  // Click Refresh rankings (load latest revision)
  const refreshBtn = errorPanel.querySelector('button');
  assert.ok(refreshBtn);
  await act(async () => {
    refreshBtn.click();
  });
  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  // Recovered on page 1 with 50 fresh items under revision 2!
  assert.equal(container.querySelector('.error-panel'), null);
  assert.equal(container.querySelectorAll('tbody tr').length, 50);
  root.unmount();
});

test('Mounted Production: 9. Production CandidatePage mounted with focused review dispatch and revision CAS', async () => {
  const { document } = setupDOM();
  const { CandidatePage, client } = await import('../.test-dist/results/Results.js');

  let reviewDispatchedWithRevision = null;
  client.getCandidate = async () => ({
    result_revision: 5,
    candidate: {
      candidate_name: 'Bob Johnson',
      candidate_source: 'doc-bob-1',
      primary_score: 85.0,
      matched_required: 2,
      total_required: 2,
      matched_preferred: 1,
      total_preferred: 1,
      evaluation_mode: 'fallback_exact',
      errors: []
    },
    final: {
      Candidate: 'Bob Johnson',
      Criteria: [
        {
          ID: 'R001',
          Requirement: 'Python Experience',
          Priority: 'required',
          Result: 'Found',
          Why: 'Demonstrated extensive Python experience in candidate resume.',
          'JD source': 'Must have Python',
          Kind: 'skill',
          'Evidence level': 'direct_verbatim',
          Checkpoints: [
            {
              Segment: 'SEG-1',
              Section: 'Experience',
              Text: '5 years of Python engineering.',
              Sources: ['doc-bob-1'],
              Why: ['direct_match'],
              'Highlight terms': ['Python'],
              'Validated against CV': true
            }
          ],
          'Display checkpoints': [],
          'Review recommended': false,
          'Processing state': 'completed',
          'Failure code': null
        }
      ],
      Notices: [],
      'Run warnings': [],
      Provisional: false,
      'Required matched': 2,
      'Required total': 2,
      'Preferred matched': 1,
      'Preferred total': 1,
      Transferable: 0,
      'Processing incomplete': 0
    },
    original_segments: [
      { segment_id: 'SEG-1', section: 'Experience', text: '5 years of Python engineering.' }
    ],
    requirements: []
  });

  client.getReviewHistory = async () => [];
  client.candidateWeighted = async () => ({
    resultRevision: 5,
    weightRevision: 5,
    result: {
      candidate_index: 0,
      candidate_id: 'cand-bob',
      candidate: 'Bob Johnson',
      status: 'completed',
      primary_score: 85.0,
      weighted_score: 85.0,
      rank: 1,
      evaluation_mode: 'fallback_exact'
    }
  });

  client.runFocusedReview = async (_ws, _jid, _cid, reqId, _prov, _useLlm, expectedRev) => {
    reviewDispatchedWithRevision = expectedRev;
    return {
      requirement_id: reqId,
      prior_verdict: 'Found',
      new_verdict: 'Found',
      result_revision: expectedRev + 1,
      explanation: 'Verified with canonical fallback assessor'
    };
  };

  const container = document.getElementById('root');
  const root = createRoot(container);
  const mockContext = {
    workspaceId: 'ws-prod',
    data: {
      workspace: { id: 'ws-prod', name: 'Production WS' },
      documents: [],
      draft: null,
      approved: null,
      weights: null,
      jobs: [],
      exports: [],
      history: []
    },
    settings: { configured_provider: 'ollama' },
    loading: false,
    error: null,
    refresh: async () => {}
  };

  await act(async () => {
    root.render(
      React.createElement(MemoryRouter, { initialEntries: ['/workspaces/ws-prod/candidate/job1/cand-bob'] },
        React.createElement(Routes, null,
          React.createElement(Route, { path: '/workspaces/:workspaceId', element: React.createElement(Outlet, { context: mockContext }) },
            React.createElement(Route, { path: 'candidate/:jobId/:candidateId', element: React.createElement(CandidatePage) })
          )
        )
      )
    );
  });

  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  assert.ok(container.textContent.includes('Bob Johnson'));
  assert.ok(container.textContent.includes('Python Experience'));

  // Click Focused review button
  const focusedBtn = Array.from(container.querySelectorAll('button')).find(b => b.textContent.includes('Focused review'));
  assert.ok(focusedBtn);

  await act(async () => {
    focusedBtn.click();
  });
  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  // Expected result revision passed to client.runFocusedReview matches candidate detail revision (5)
  assert.equal(reviewDispatchedWithRevision, 5);
  assert.ok(container.textContent.includes('Focused review completed'));
  root.unmount();
});

test('Mounted Production: 10. Production ProgressPage mounted with resume control dispatch', async () => {
  const { document } = setupDOM();
  const { ProgressPage, client } = await import('../.test-dist/results/Results.js');

  let resumedJobControl = null;
  client.getJob = async () => ({
    id: 'job-prog-p10',
    workspace_id: 'ws-prod',
    kind: 'assess',
    state: 'cancelled',
    progress: 10,
    total: 50,
    created: '2026-11-16T00:00:00Z',
    updated: '2026-11-16T00:00:00Z',
    message: 'Cancelled by user',
    request_json: '{}'
  });

  client.listRankings = async () => ({
    items: [],
    total: 50,
    offset: 0,
    limit: 50,
    officialCount: 10,
    unfinishedCount: 40,
    resultRevision: 1,
    weightRevision: 1
  });

  client.controlJob = async (wsId, jid, action) => {
    resumedJobControl = { wsId, jid, action };
    return { id: jid, state: 'pending' };
  };

  const container = document.getElementById('root');
  const root = createRoot(container);
  const mockContext = {
    workspaceId: 'ws-prod',
    data: {
      workspace: { id: 'ws-prod', name: 'Production WS' },
      documents: [],
      draft: null,
      approved: null,
      weights: null,
      jobs: [{ id: 'job-prog-p10', state: 'cancelled' }],
      exports: [],
      history: []
    },
    settings: { configured_provider: 'ollama' },
    loading: false,
    error: null,
    refresh: async () => {}
  };

  await act(async () => {
    root.render(
      React.createElement(MemoryRouter, { initialEntries: ['/workspaces/ws-prod/progress/job-prog-p10'] },
        React.createElement(Routes, null,
          React.createElement(Route, { path: '/workspaces/:workspaceId', element: React.createElement(Outlet, { context: mockContext }) },
            React.createElement(Route, { path: 'progress/:jobId', element: React.createElement(ProgressPage) })
          )
        )
      )
    );
  });

  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  assert.ok(container.textContent.includes('10 of 50 committed'));
  const resumeBtn = Array.from(container.querySelectorAll('button')).find(b => b.textContent.includes('Resume eligible work'));
  assert.ok(resumeBtn);

  await act(async () => {
    resumeBtn.click();
  });
  await act(async () => {
    await new Promise(r => globalThis.setTimeout(r, 60));
  });

  assert.deepEqual(resumedJobControl, {
    wsId: 'ws-prod',
    jid: 'job-prog-p10',
    action: 'resume'
  });
  assert.ok(container.textContent.includes('Job requeued with existing checkpoints preserved'));
  root.unmount();
});
