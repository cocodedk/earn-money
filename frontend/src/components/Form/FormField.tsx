import {
  Children,
  cloneElement,
  isValidElement,
  ReactElement,
  ReactNode,
} from "react";
import styles from "./Form.module.css";

export type FormFieldProps = {
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
};

export function FormField({
  label,
  htmlFor,
  error,
  required,
  children,
}: FormFieldProps) {
  const errorId = `${htmlFor}-error`;
  const child = Children.only(children) as ReactElement<{
    "aria-invalid"?: boolean;
    "aria-describedby"?: string;
    "data-invalid"?: boolean;
  }>;
  const enhancedChild = isValidElement(child)
    ? cloneElement(child, {
        "aria-invalid": Boolean(error),
        "aria-describedby": error ? errorId : undefined,
        "data-invalid": Boolean(error),
      })
    : child;
  return (
    <div className={styles.field}>
      <label htmlFor={htmlFor} className={styles.label}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {enhancedChild}
      {error && (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  );
}
