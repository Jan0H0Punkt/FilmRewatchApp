# Todo

- Change the layout design to look like VS Code or my SportsApp.
- Show the average rating permanently in the film detail view, not only on hover.
- The library view's sorting doesn't update live: after editing a film, or after a Letterboxd sync where I click accept, the list keeps its old order until a reload. Find out why the view doesn't re-render (possibly signals that don't notice nested changes).
- The library view renders every film at once. Render only the visible part instead, like Android's RecyclerView (virtual scrolling, e.g. `cdk-virtual-scroll-viewport` from the already-installed `@angular/cdk`), or at least load 50 more each time the user scrolls near the end.
