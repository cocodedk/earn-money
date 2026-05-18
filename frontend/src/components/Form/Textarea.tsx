import { TextareaHTMLAttributes } from "react";
import styles from "./Form.module.css";

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea(props: TextareaProps) {
  return <textarea className={styles.textarea} {...props} />;
}
