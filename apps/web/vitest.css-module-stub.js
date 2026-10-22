/** Proxy so `styles.paper` → `"paper"` during unit tests. */
module.exports = new Proxy(
  {},
  {
    get(_target, prop) {
      if (prop === "__esModule") return false;
      if (prop === "default") {
        return new Proxy(
          {},
          {
            get(_t, p) {
              return typeof p === "string" ? p : undefined;
            },
          },
        );
      }
      return typeof prop === "string" ? prop : undefined;
    },
  },
);
