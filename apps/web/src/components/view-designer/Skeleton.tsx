import styles from "./ViewDesigner.module.css";

/** Loading state shaped like a form screen (SPEC 8): title, tabs, two columns of fields. */
export function CanvasSkeleton({ label = "Loading the screen from Odoo…" }: { label?: string }) {
  const col = (n: number) => (
    <div className={styles.skelCol}>
      {Array.from({ length: n }, (_, i) => <div key={i} className={styles.skelBar} data-w={i % 2 ? "short" : undefined} />)}
    </div>
  );
  return (
    <div className={styles.skeleton} role="status" aria-busy="true" data-testid="vd-skeleton">
      <span className={styles.srOnly}>{label}</span>
      <div className={styles.skelBar} data-w="title" />
      <div className={styles.skelRow}>{col(4)}{col(4)}</div>
      <div className={styles.skelBar} data-w="tabs" />
      <div className={styles.skelRow}>{col(3)}{col(3)}</div>
    </div>
  );
}
