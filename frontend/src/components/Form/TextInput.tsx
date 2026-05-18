import { InputHTMLAttributes } from "react";
import styles from "./Form.module.css";

export type TextInputProps = InputHTMLAttributes<HTMLInputElement>;

export function TextInput(props: TextInputProps) {
  return <input type="text" className={styles.input} {...props} />;
}
