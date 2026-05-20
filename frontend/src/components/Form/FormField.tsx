import { cloneElement, ReactElement } from "react";
import styles from "./Form.module.css";

type FieldInputProps = {
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  "data-invalid"?: boolean;
};

export type FormFieldProps = {
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
  children: ReactElement<FieldInputProps>;
};

export function FormField({
  label,
  htmlFor,
  error,
  required,
  children,
}: FormFieldProps) {
  const errorId = `${htmlFor}-error`;
  const enhancedChild = cloneElement(children, {
    "aria-invalid": Boolean(error),
    "aria-describedby": error ? errorId : undefined,
    "data-invalid": Boolean(error),
  });
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
