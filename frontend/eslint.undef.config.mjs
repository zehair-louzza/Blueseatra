// Contrôle CI « identifiants non définis » (05/10/2026).
// Né de la page blanche du 05/10/2026 (PR #181 → #182) : une icône utilisée
// sans import compile sans erreur mais fait planter React au premier rendu.
// Volontairement étroit : seules les erreurs qui CASSENT l'application à
// l'exécution, pour bloquer la fusion sans bruit de style.
import react from "eslint-plugin-react";
import globals from "globals";

export default [
  { ignores: ["build/**", "node_modules/**", "public/**"] },
  {
    files: ["src/**/*.{js,jsx}"],
    plugins: { react },
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.jest, process: "readonly" },
    },
    linterOptions: { reportUnusedDisableDirectives: "off" },
    rules: {
      "no-undef": "error",              // variable non définie
      "react/jsx-no-undef": "error",    // composant JSX non importé
      "react/jsx-uses-vars": "error",   // ne pas compter un import JSX comme inutilisé
      "react/jsx-uses-react": "error",
    },
  },
];
