{
  "brand": {
    "name": "Blueseatra",
    "attributes": [
      "trustworthy",
      "traceable",
      "fast",
      "calmly data-dense",
      "international-ready (FR/EN)"
    ],
    "visual_personality": {
      "style_fusion": [
        "Swiss/International Typographic Style (clarity + grid discipline)",
        "Modern enterprise SaaS (dense tables + progressive disclosure)",
        "Soft coastal minimalism (warm sand surfaces + ocean accents)",
        "Subtle glass (only for overlays/drawers, not content cards)"
      ],
      "do_not": [
        "No purple for AI/chat vibes.",
        "No heavy gradients; keep gradients decorative and under 20% viewport.",
        "No centered app container layouts.",
        "No transition: all."
      ]
    }
  },

  "information_architecture": {
    "public_marketing": [
      "Home/Landing",
      "Use cases (construction/trades/services)",
      "How it works (Upload → Extract → Match → Validate → Quote)",
      "Plans",
      "Security/Compliance (lightweight trust section)",
      "Contact",
      "Login/Signup"
    ],
    "authenticated_console": {
      "global_shell": [
        "Top bar: tenant switcher + global search + language toggle + user menu",
        "Left nav: Dashboard, Requests, Catalogs, Quotes, Members, Audit log, Settings, Billing"
      ],
      "core_pages": [
        "Dashboard (KPIs + recent activity)",
        "Requests list + Request detail (doc viewer + extracted fields + matching)",
        "Catalogs list + CSV import wizard (versioning)",
        "Quote drafts list",
        "Quote editor/detail (line items + VAT + totals + PDF)",
        "Admin: members + roles",
        "Audit log timeline",
        "Settings: integrations (AI provider/model + n8n webhooks)",
        "Billing placeholder"
      ]
    },
    "success_actions": [
      "Upload a request document",
      "Import/activate a pricing catalog version",
      "Confirm AI matches and generate a quote PDF",
      "Switch tenant and keep auditability"
    ]
  },

  "i18n_guidelines": {
    "library": "react-i18next",
    "languages": ["fr", "en"],
    "layout_rules": [
      "Design for 30–40% longer strings (FR often longer than EN).",
      "Buttons must allow wrapping on mobile (no fixed widths).",
      "Tables: prefer column min-width + horizontal scroll on mobile via ScrollArea.",
      "Numbers/currency: format with Intl.NumberFormat per locale (EUR default, but tenant-configurable later).",
      "Dates: Intl.DateTimeFormat per locale; show relative time in lists (e.g., 'il y a 2 h' / '2h ago')."
    ],
    "language_toggle_ui": {
      "placement": "Top bar right side, near user menu",
      "component": "Switch or DropdownMenu",
      "labeling": "FR / EN short labels; include sr-only full label",
      "data_testid": "language-toggle"
    }
  },

  "design_tokens": {
    "color_system": {
      "mode": "light-first (optional dark later)",
      "semantic_tokens_hsl_for_shadcn": {
        "background": "36 45% 97%",
        "foreground": "210 22% 14%",
        "card": "0 0% 100%",
        "card-foreground": "210 22% 14%",
        "popover": "0 0% 100%",
        "popover-foreground": "210 22% 14%",

        "primary": "210 55% 22%",
        "primary-foreground": "0 0% 98%",

        "secondary": "210 20% 96%",
        "secondary-foreground": "210 30% 18%",

        "muted": "210 18% 95%",
        "muted-foreground": "215 16% 42%",

        "accent": "186 34% 40%",
        "accent-foreground": "0 0% 98%",

        "border": "210 18% 88%",
        "input": "210 18% 88%",
        "ring": "186 34% 40%",

        "destructive": "0 72% 52%",
        "destructive-foreground": "0 0% 98%",

        "radius": "0.75rem"
      },
      "brand_hex_reference": {
        "navy_ink": "#1A2B45",
        "ocean_teal": "#3F8F8A",
        "sea_mist": "#E7F3F2",
        "sand_bg": "#FBF7F1",
        "slate_text": "#2C3E50",
        "muted_slate": "#6A7B8A",
        "border_gray": "#DDE3EA",
        "success": "#1F8A5B",
        "warning": "#B7791F",
        "info": "#2563EB"
      },
      "status_badges": {
        "request_status": {
          "received": {"bg": "bg-slate-100", "text": "text-slate-700", "ring": "ring-slate-200"},
          "processing": {"bg": "bg-sky-50", "text": "text-sky-700", "ring": "ring-sky-200"},
          "needs_review": {"bg": "bg-amber-50", "text": "text-amber-800", "ring": "ring-amber-200"},
          "done": {"bg": "bg-emerald-50", "text": "text-emerald-800", "ring": "ring-emerald-200"},
          "failed": {"bg": "bg-rose-50", "text": "text-rose-800", "ring": "ring-rose-200"}
        },
        "match_status": {
          "matched": {"bg": "bg-emerald-50", "text": "text-emerald-800", "ring": "ring-emerald-200"},
          "proposed": {"bg": "bg-sky-50", "text": "text-sky-800", "ring": "ring-sky-200"},
          "to_confirm": {"bg": "bg-amber-50", "text": "text-amber-900", "ring": "ring-amber-200"},
          "no_match": {"bg": "bg-slate-100", "text": "text-slate-700", "ring": "ring-slate-200"}
        },
        "quote_status": {
          "draft": {"bg": "bg-slate-100", "text": "text-slate-700", "ring": "ring-slate-200"},
          "validated": {"bg": "bg-emerald-50", "text": "text-emerald-800", "ring": "ring-emerald-200"},
          "sent": {"bg": "bg-sky-50", "text": "text-sky-800", "ring": "ring-sky-200"}
        }
      },
      "gradients_and_texture": {
        "allowed_gradients": [
          {
            "name": "Ocean Mist (hero only)",
            "css": "linear-gradient(135deg, rgba(26,43,69,0.10) 0%, rgba(63,143,138,0.12) 55%, rgba(251,247,241,0.0) 100%)",
            "usage": "Marketing hero background overlay only; keep under 20% viewport and behind text."
          },
          {
            "name": "Sea Glass (decorative strip)",
            "css": "linear-gradient(90deg, rgba(63,143,138,0.18) 0%, rgba(231,243,242,0.0) 70%)",
            "usage": "Thin accent strip at section edges or behind icons; never behind paragraphs."
          }
        ],
        "noise_overlay": {
          "css_snippet": ":root{--noise-opacity:0.035;} .noise-bg{position:relative;} .noise-bg:before{content:'';position:absolute;inset:0;pointer-events:none;background-image:url('/noise.png');opacity:var(--noise-opacity);mix-blend-mode:multiply;}",
          "note": "Prefer a tiny 128–256px seamless noise PNG. If not available, skip rather than faking heavy noise."
        }
      }
    },

    "typography": {
      "font_pairing": {
        "headings": "Space Grotesk (600/700)",
        "body": "Inter (400/500)",
        "mono": "IBM Plex Mono (for IDs, CSV mapping, code/webhooks)"
      },
      "implementation": {
        "google_fonts": [
          "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap"
        ],
        "css_vars": {
          "--font-sans": "Inter, ui-sans-serif, system-ui",
          "--font-display": "Space Grotesk, ui-sans-serif, system-ui",
          "--font-mono": "IBM Plex Mono, ui-monospace, SFMono-Regular"
        }
      },
      "scale_tailwind": {
        "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
        "h2": "text-base md:text-lg text-muted-foreground",
        "section_title": "text-xl md:text-2xl font-semibold tracking-tight",
        "card_title": "text-sm font-semibold",
        "body": "text-sm md:text-base leading-6",
        "meta": "text-xs text-muted-foreground",
        "mono": "font-mono text-xs"
      }
    },

    "spacing_and_layout": {
      "principles": [
        "Use 2–3x more whitespace than default admin templates.",
        "Prefer 12-col grid on desktop, single column on mobile.",
        "Data-dense areas use consistent row heights and sticky headers."
      ],
      "container": {
        "marketing": "max-w-6xl mx-auto px-4 sm:px-6 lg:px-8",
        "console": "w-full px-3 sm:px-4 lg:px-6"
      },
      "grid": {
        "desktop": "grid grid-cols-12 gap-4 lg:gap-6",
        "bento_cards": "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4"
      },
      "radii": {
        "card": "rounded-xl",
        "button": "rounded-lg",
        "input": "rounded-md",
        "drawer": "rounded-t-2xl md:rounded-2xl"
      },
      "shadows": {
        "card": "shadow-[0_1px_0_rgba(16,24,40,0.04),0_8px_24px_rgba(16,24,40,0.06)]",
        "popover": "shadow-[0_12px_40px_rgba(16,24,40,0.14)]"
      }
    }
  },

  "components": {
    "component_path": {
      "button": "/app/frontend/src/components/ui/button.jsx",
      "input": "/app/frontend/src/components/ui/input.jsx",
      "textarea": "/app/frontend/src/components/ui/textarea.jsx",
      "select": "/app/frontend/src/components/ui/select.jsx",
      "switch": "/app/frontend/src/components/ui/switch.jsx",
      "badge": "/app/frontend/src/components/ui/badge.jsx",
      "card": "/app/frontend/src/components/ui/card.jsx",
      "table": "/app/frontend/src/components/ui/table.jsx",
      "tabs": "/app/frontend/src/components/ui/tabs.jsx",
      "dialog": "/app/frontend/src/components/ui/dialog.jsx",
      "drawer": "/app/frontend/src/components/ui/drawer.jsx",
      "sheet": "/app/frontend/src/components/ui/sheet.jsx",
      "dropdown_menu": "/app/frontend/src/components/ui/dropdown-menu.jsx",
      "command": "/app/frontend/src/components/ui/command.jsx",
      "scroll_area": "/app/frontend/src/components/ui/scroll-area.jsx",
      "separator": "/app/frontend/src/components/ui/separator.jsx",
      "progress": "/app/frontend/src/components/ui/progress.jsx",
      "skeleton": "/app/frontend/src/components/ui/skeleton.jsx",
      "calendar": "/app/frontend/src/components/ui/calendar.jsx",
      "sonner_toast": "/app/frontend/src/components/ui/sonner.jsx"
    },

    "global_shell_patterns": {
      "topbar": {
        "layout": "h-14 flex items-center justify-between gap-3 px-3 sm:px-4 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60",
        "left": [
          "Logo wordmark (Blueseatra)",
          "Tenant switcher (DropdownMenu + Command search)"
        ],
        "center": [
          "Global search (Command) for Requests/Quotes/Catalog items"
        ],
        "right": [
          "Language toggle",
          "Notifications (optional)",
          "User menu"
        ]
      },
      "sidebar": {
        "desktop": "w-64 border-r bg-background",
        "mobile": "Sheet from left with same nav",
        "nav_item": "flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "active": "bg-muted text-foreground font-medium"
      }
    },

    "buttons": {
      "variants": {
        "primary": {
          "use": "Primary actions: Upload request, Import CSV, Generate PDF, Validate quote",
          "tailwind": "bg-primary text-primary-foreground hover:bg-primary/90",
          "motion": "hover:translate-y-[-1px] active:translate-y-0 active:scale-[0.99] transition-colors"
        },
        "secondary": {
          "use": "Secondary actions: Preview, Save draft",
          "tailwind": "bg-secondary text-secondary-foreground hover:bg-secondary/80",
          "motion": "transition-colors"
        },
        "ghost": {
          "use": "Toolbar actions, table row actions",
          "tailwind": "hover:bg-muted",
          "motion": "transition-colors"
        },
        "destructive": {
          "use": "Delete catalog version, remove line",
          "tailwind": "bg-destructive text-destructive-foreground hover:bg-destructive/90",
          "motion": "transition-colors"
        }
      },
      "sizes": {
        "sm": "h-8 px-3 text-xs",
        "md": "h-9 px-4 text-sm",
        "lg": "h-10 px-5 text-sm"
      },
      "data_testid_examples": [
        "data-testid=\"request-upload-button\"",
        "data-testid=\"catalog-import-next-button\"",
        "data-testid=\"quote-generate-pdf-button\""
      ]
    },

    "forms": {
      "inputs": {
        "rule": "Always show label + helper text for complex fields (webhooks, model selector).",
        "error": "Use Form + error message text-xs text-destructive; also set aria-invalid.",
        "focus": "Use ring-ring; ensure visible focus on all controls."
      },
      "file_dropzone": {
        "component": "Card + dashed border + Input(type=file) hidden",
        "tailwind": "rounded-xl border border-dashed border-border bg-card hover:bg-muted/40 transition-colors",
        "states": {
          "idle": "Show supported formats + max size",
          "drag_over": "border-ring bg-accent/10",
          "uploading": "Progress + cancel",
          "done": "Show file chip + replace"
        },
        "data_testid": "file-dropzone"
      }
    },

    "tables_and_density": {
      "pattern": "Table as primary work surface; details open in Drawer/Sheet for progressive disclosure.",
      "table_toolbar": [
        "Search input",
        "Status filter (Select)",
        "Date range (Calendar in Popover)",
        "Column visibility (DropdownMenu)",
        "Primary CTA on right"
      ],
      "row_interaction": {
        "hover": "hover:bg-muted/50",
        "selected": "data-[state=selected]:bg-accent/10",
        "click": "Row click opens detail drawer; keep explicit 'Open' action for accessibility"
      },
      "mobile": "Wrap table in ScrollArea; show key columns only; move secondary columns into row 'More' Drawer.",
      "data_testid": {
        "table": "requests-table",
        "row": "requests-table-row",
        "filter": "requests-status-filter",
        "search": "requests-search-input"
      }
    },

    "wizards": {
      "csv_import_stepper": {
        "steps": [
          "Upload",
          "Detect",
          "Preview",
          "Mapping",
          "Validate",
          "Errors",
          "Activate"
        ],
        "component": "Tabs (for desktop) + Progress (for mobile) + sticky footer actions",
        "sticky_footer": "fixed bottom-0 left-0 right-0 border-t bg-background/90 backdrop-blur px-3 py-3",
        "error_log": "Use Table with row-level error badges + downloadable CSV of errors",
        "data_testid": "catalog-import-stepper"
      }
    },

    "quote_editor": {
      "layout": {
        "desktop": "Split view: left line-items table (8 cols), right totals + actions (4 cols) sticky",
        "mobile": "Single column; totals in Accordion at bottom; actions sticky"
      },
      "line_item_row": {
        "columns": [
          "Catalog item (Select/Command)",
          "Description (editable)",
          "Qty",
          "Unit",
          "Unit price (from catalog)",
          "VAT",
          "Match score badge + reason tooltip",
          "Row total"
        ],
        "explainability": {
          "ui": "Badge with score (e.g., 92%) + Tooltip for reason + 'Confirm' toggle",
          "rule": "Always show 'Pricing source: Catalog vX' in meta text; never imply AI invented price."
        },
        "data_testid": {
          "add_line": "quote-add-line-button",
          "line_row": "quote-line-item-row",
          "match_badge": "quote-line-match-badge",
          "totals": "quote-totals-panel"
        }
      }
    },

    "audit_timeline": {
      "component": "Card list with left border accent + timestamp + actor + action",
      "tailwind": "relative pl-4 before:absolute before:left-0 before:top-0 before:bottom-0 before:w-px before:bg-border",
      "data_testid": "audit-log-timeline"
    },

    "toasts": {
      "library": "sonner",
      "rules": [
        "Use success toast for 'Catalog version activated', 'Quote PDF generated'.",
        "Use destructive toast for failed imports with 'View errors' action.",
        "Keep copy bilingual-ready (short strings)."
      ]
    }
  },

  "motion_and_microinteractions": {
    "library": "framer-motion",
    "principles": [
      "Use motion to clarify state changes (uploading → processed, drawer open, step transitions).",
      "Prefer 120–180ms for hover/focus color transitions; 180–240ms for drawers/dialogs.",
      "Respect prefers-reduced-motion: reduce (disable parallax and large transitions)."
    ],
    "recommended_patterns": {
      "drawer": "Slide + fade (y: 12 → 0, opacity 0 → 1)",
      "table_row": "Subtle background fade on hover only (no transform)",
      "kpi_cards": "Entrance stagger on dashboard load (small y + opacity)",
      "upload": "Progress bar + rotating loader icon (lucide)"
    }
  },

  "accessibility": {
    "wcag": "AA",
    "rules": [
      "All controls must have visible focus (ring-2 ring-ring).",
      "Use aria-label for icon-only buttons.",
      "Ensure status is not color-only: pair badge color with text label.",
      "Tables: keep header semantics; provide scope and accessible row actions.",
      "Language toggle must set lang attribute on html/body if possible."
    ]
  },

  "image_urls": {
    "marketing": {
      "hero_background": {
        "description": "Abstract coastal texture (very subtle) used as decorative background behind hero; keep readable.",
        "urls": [
          "(optional) Use a self-hosted subtle noise/texture; avoid busy photos for B2B console."
        ]
      },
      "use_case_illustrations": {
        "description": "Simple line/duotone illustrations (documents → structured data → quote). Prefer Lottie over photos.",
        "urls": [
          "https://lottiefiles.com/search?q=document%20upload",
          "https://lottiefiles.com/search?q=invoice",
          "https://lottiefiles.com/search?q=workflow"
        ]
      }
    }
  },

  "libraries_and_setup": {
    "recommended": [
      {
        "name": "react-i18next",
        "why": "Multilingual UI FR/EN",
        "install": "npm i i18next react-i18next",
        "usage": "Create i18n.js, wrap app with I18nextProvider, use useTranslation() in components."
      },
      {
        "name": "framer-motion",
        "why": "Micro-interactions and page transitions",
        "install": "npm i framer-motion",
        "usage": "Use motion.div for drawers/cards; gate with prefers-reduced-motion."
      }
    ]
  },

  "instructions_to_main_agent": [
    "Replace the default CRA App.css centered dark header styles; do not center the app container.",
    "Update index.css :root tokens to the provided HSL semantic tokens (light-first).",
    "Implement a consistent AppShell: Topbar + Sidebar (Sheet on mobile).",
    "Use shadcn/ui components from /src/components/ui only (no raw HTML dropdowns/calendars/toasts).",
    "All interactive and key informational elements MUST include data-testid in kebab-case.",
    "For data-dense screens: use Table + Toolbar + Drawer detail pattern (progressive disclosure).",
    "For CSV import: implement stepper with sticky footer actions and an explicit error log table.",
    "For quote editor: split layout with sticky totals panel; show match score + reason tooltip; always show catalog version as pricing source.",
    "Ensure i18n: allow longer strings, avoid fixed widths, and format dates/numbers with Intl per locale."
  ]
}

<General UI UX Design Guidelines>  
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts"
  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.
</General UI UX Design Guidelines>
