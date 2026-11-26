export async function fetchAllPages(listFn, params = {}) {
  const results = [];
  let page = Number(params.page) || 1;
  const visitedPages = new Set();

  for (let pageCount = 0; pageCount < 1000; pageCount += 1) {
    if (visitedPages.has(page)) {
      throw new Error('Pagination loop detected while loading records');
    }
    visitedPages.add(page);

    const response = await listFn({ ...params, page });
    if (Array.isArray(response)) {
      results.push(...response);
      return results;
    }

    const pageResults = Array.isArray(response?.results) ? response.results : [];
    results.push(...pageResults);
    if (!response?.next) return results;

    let nextPage = page + 1;
    try {
      const nextUrl = new URL(response.next, window.location.origin);
      const parsedPage = Number(nextUrl.searchParams.get('page'));
      if (Number.isInteger(parsedPage) && parsedPage > 0) nextPage = parsedPage;
    } catch {
      // Fall back to sequential page numbers for an unparseable next link.
    }
    page = nextPage;
  }

  throw new Error('Pagination exceeded the safety limit while loading records');
}
