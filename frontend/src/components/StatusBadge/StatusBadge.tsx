export type StatusBadgeProps<S extends string> = {
  status: S;
  palette: Record<S, string>;
};

export function StatusBadge<S extends string>({
  status,
  palette,
}: StatusBadgeProps<S>) {
  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${palette[status]}`}
    >
      {status}
    </span>
  );
}
