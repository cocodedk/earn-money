import styles from "./FiltersBar.module.css";

export type FilterOption = { value: string; label: string };

export type FilterDef = {
  key: string;
  label: string;
  options: FilterOption[];
};

export type FiltersBarProps = {
  filters: FilterDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
};

export function FiltersBar({ filters, values, onChange }: FiltersBarProps) {
  return (
    <div className={styles.bar}>
      {filters.map((filter) => {
        const value = values[filter.key] ?? "";
        const inputId = `filter-${filter.key}`;
        return (
          <label key={filter.key} className={styles.filter} htmlFor={inputId}>
            <span className={styles.label}>{filter.label}</span>
            {filter.options.length > 0 ? (
              <select
                id={inputId}
                className={styles.select}
                value={value}
                onChange={(e) => onChange(filter.key, e.target.value)}
              >
                <option value="">All</option>
                {filter.options.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={inputId}
                type="text"
                className={styles.input}
                value={value}
                onChange={(e) => onChange(filter.key, e.target.value)}
              />
            )}
          </label>
        );
      })}
    </div>
  );
}
