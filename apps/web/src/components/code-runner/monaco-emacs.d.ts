declare module "monaco-emacs" {
  import type * as Monaco from "monaco-editor";
  export class EmacsExtension {
    constructor(editor: Monaco.editor.IStandaloneCodeEditor);
    start(): void;
    dispose(): void;
  }
}
