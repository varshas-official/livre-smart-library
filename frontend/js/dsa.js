/* DSA workbench for LIVRE. Core algorithms live in backend/dsa_algorithms.py. */
window.loadDSAPage = async function () {
  const results = await Promise.all([api('/api/dsa/catalogue?limit=60'),api('/api/dsa/analysis'),api('/api/reservations')]);
  const catalogue = results[0], analysis = results[1], reservationData = results[2];
  const reservationRows = reservationData.items.map(function (r) {
    const pending = r.status === 'pending';
    const position = pending ? 'Queue position ' + r.queue_position : (r.status === 'fulfilled' ? 'Fulfilled' : 'Cancelled');
    return '<tr><td>' + esc(r.title) + '</td><td>' + esc(r.status) + '</td><td>' + esc(position) + '</td><td>' +
      (pending ? '<button class="button button-quiet" data-cancel-reservation="' + r.id + '">Cancel</button>' : '—') + '</td></tr>';
  }).join('');
  const bstRows = catalogue.items.map(function (b) {
    return '<tr><td>' + b.id + '</td><td>' + esc(b.title) + '</td><td>' + esc(b.isbn || '—') + '</td><td>' + b.available_copies + ' / ' + b.total_copies + '</td></tr>';
  }).join('');
  const sortRows = analysis.merge_sort_preview.map(function (b, i) {
    return '<tr><td>' + (i + 1) + '</td><td>' + esc(b.title) + '</td><td>' + esc(b.category) + '</td></tr>';
  }).join('');
  const body =
    '<section class="dsa-grid">' +
      '<article class="dsa-panel dsa-lookup"><div class="dsa-eyebrow">HASH TABLE · EXACT LOOKUP</div><h2>Find a book by ID or ISBN</h2><p>Uses a manually implemented hash table with separate chaining for collisions.</p>' +
        '<form id="dsa-lookup-form" class="dsa-form"><label for="dsa-key">Book ID or ISBN</label><div class="dsa-input-row"><input id="dsa-key" name="key" required placeholder="e.g. 4 or ISBN:9780131103627"><button class="button button-primary" type="submit">Search index</button></div><small>Use ID:4 or ISBN:978-… to disambiguate the key.</small></form><div id="dsa-lookup-result" class="dsa-result" aria-live="polite">Enter a key to inspect the hash-table lookup.</div></article>' +
      '<article class="dsa-panel"><div class="dsa-eyebrow">ALGORITHM ANALYSIS</div><h2>Search comparison</h2><p>Same target, two lookup approaches. Counts show key comparisons, not wall-clock time.</p><div class="dsa-metrics"><div><small>Linear search</small><strong>' + analysis.linear_search_comparisons + '</strong><span>comparisons</span></div><div><small>Hash lookup</small><strong>' + analysis.hash_lookup_comparisons + '</strong><span>chain comparisons</span></div></div><p class="dsa-note">The hash index is built from ' + analysis.hash_index_build_records + ' books before lookup; building it costs O(B). Lookup is expected O(1), worst-case O(B).</p></article>' +
      '<article class="dsa-panel"><div class="dsa-eyebrow">BINARY SEARCH TREE</div><h2>Catalogue in title order</h2><p>The backend inserts book records into a BST and displays them using in-order traversal.</p><div class="dsa-metrics three"><div><small>Nodes</small><strong>' + catalogue.bst_nodes + '</strong></div><div><small>Height</small><strong>' + catalogue.bst_height + '</strong></div><div><small>Insert comparisons</small><strong>' + catalogue.insert_comparisons + '</strong></div></div><div class="dsa-table-wrap"><table class="data-table"><thead><tr><th>ID</th><th>Title (in-order)</th><th>ISBN</th><th>Copies</th></tr></thead><tbody>' + bstRows + '</tbody></table></div></article>' +
      '<article class="dsa-panel"><div class="dsa-eyebrow">MERGE SORT</div><h2>Catalogue sorted by title</h2><p>The same records are sorted using Merge Sort so the implementation and comparison count can be discussed.</p><div class="dsa-metrics"><div><small>Merge Sort comparisons</small><strong>' + analysis.merge_sort_comparisons + '</strong></div><div><small>Records sorted</small><strong>' + analysis.catalogue_count + '</strong></div></div><div class="dsa-table-wrap"><table class="data-table"><thead><tr><th>#</th><th>Title</th><th>Category</th></tr></thead><tbody>' + sortRows + '</tbody></table></div><p class="dsa-note">Merge Sort runs in O(B log B) time and O(B) auxiliary space.</p></article>' +
      '<article class="dsa-panel dsa-reservations"><div class="dsa-eyebrow">FIFO QUEUE</div><h2>My reservation queue</h2><p>When a title is unavailable, members can join its reservation line. The earliest pending request has first borrowing priority when a copy becomes available.</p>' +
      (reservationRows ? '<div class="dsa-table-wrap"><table class="data-table"><thead><tr><th>Title</th><th>Status</th><th>Queue position</th><th>Action</th></tr></thead><tbody>' + reservationRows + '</tbody></table></div>' : '<div class="dsa-empty">No reservations yet. Visit Search Books and choose “Join queue” on an unavailable title.</div>') +
      '<p class="dsa-note">Reservation requests are persisted in SQLite. The custom circular FIFO queue reconstructs their order; queue enqueue/dequeue operations are O(1), while loading persisted requests costs O(Q).</p></article>' +
    '</section>';
  layout('DSA Lab', 'Explore the data structures and algorithms powering the library catalogue.', body, 'ALGORITHMS IN ACTION');
  document.querySelector('#dsa-lookup-form').addEventListener('submit', async function (event) {
    event.preventDefault();
    const key = document.querySelector('#dsa-key').value.trim();
    const output = document.querySelector('#dsa-lookup-result');
    output.textContent = 'Searching the indexed catalogue…';
    try {
      const result = await api('/api/dsa/lookup?key=' + encodeURIComponent(key));
      if (!result.found) {
        output.innerHTML = '<strong>No matching book.</strong><p>Bucket-chain comparisons: ' + result.lookup_comparisons + ' · hash collisions during index build: ' + result.hash_collisions + '</p>';
      } else {
        output.innerHTML = '<strong>' + esc(result.book.title) + '</strong><p>Book ID: ' + result.book.id + ' · ISBN: ' + esc(result.book.isbn || '—') + '</p><p>Category: ' + esc(result.book.category) + ' · Copies available: ' + result.book.available_copies + '</p><p>Bucket-chain comparisons: ' + result.lookup_comparisons + ' · Index collisions: ' + result.hash_collisions + '</p>';
      }
    } catch (error) { output.textContent = error.message; }
  });
  drawIcons();
};

document.body.addEventListener('click', async function (event) {
  const reserveButton = event.target.closest('[data-reserve]');
  if (reserveButton) {
    event.preventDefault();
    reserveButton.disabled = true;
    try {
      const result = await api('/api/reservations', { method: 'POST', body: JSON.stringify({ book_id: Number(reserveButton.dataset.reserve) }) });
      notify(result.message + ' Queue position: ' + result.queue_position + '.', false);
      if (location.hash === '#dsa') await window.loadDSAPage();
      else if (typeof route === 'function') await route();
    } catch (error) {
      notify(error.message, true);
      reserveButton.disabled = false;
    }
    return;
  }
  const cancelButton = event.target.closest('[data-cancel-reservation]');
  if (cancelButton) {
    cancelButton.disabled = true;
    try {
      const result = await api('/api/reservations/' + cancelButton.dataset.cancelReservation, { method: 'DELETE' });
      notify(result.message, false);
      await window.loadDSAPage();
    } catch (error) {
      notify(error.message, true);
      cancelButton.disabled = false;
    }
  }
});
