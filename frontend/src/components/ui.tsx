import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as SelectPrimitive from "@radix-ui/react-select";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as ToastPrimitive from "@radix-ui/react-toast";
import ReactMarkdown from "react-markdown";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
  type SortingState,
} from "@tanstack/react-table";
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  CircleAlert,
  Command,
  Search,
  X,
} from "lucide-react";
import {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  TextareaHTMLAttributes,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type ButtonVariant = "solid" | "outline" | "quiet" | "danger";
export function Button({
  variant = "solid",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button className={`ui-button ui-${variant} ${className}`} {...props} />
  );
}
export const Input = React.forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className = "", ...props }, ref) => (
  <input ref={ref} className={`ui-input ${className}`} {...props} />
));
Input.displayName = "Input";
export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className = "", ...props }, ref) => (
  <textarea ref={ref} className={`ui-textarea ${className}`} {...props} />
));
Textarea.displayName = "Textarea";
export function Select({
  value,
  onValueChange,
  options,
  placeholder = "Seleccionar…",
  disabled,
}: {
  value?: string;
  onValueChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <SelectPrimitive.Root
      value={value}
      onValueChange={onValueChange}
      disabled={disabled}
    >
      <SelectPrimitive.Trigger className="ui-select">
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon>
          <ChevronDown size={14} />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          className="ui-select-content"
          position="popper"
        >
          <SelectPrimitive.Viewport>
            {options.map((o) => (
              <SelectPrimitive.Item
                className="ui-select-item"
                value={o.value}
                key={o.value}
              >
                <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator>
                  <Check size={13} />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
export function Checkbox({
  checked,
  onCheckedChange,
  label,
  disabled,
}: {
  checked?: boolean;
  onCheckedChange?: (v: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <label className="ui-check-wrap">
      <CheckboxPrimitive.Root
        className="ui-checkbox"
        checked={checked}
        onCheckedChange={(v) => onCheckedChange?.(v === true)}
        disabled={disabled}
      >
        <CheckboxPrimitive.Indicator>
          <Check size={13} />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {label && <span>{label}</span>}
    </label>
  );
}
export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <label className="ui-switch-wrap">
      <SwitchPrimitive.Root
        className="ui-switch"
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
      >
        <SwitchPrimitive.Thumb className="ui-switch-thumb" />
      </SwitchPrimitive.Root>
      {label && <span>{label}</span>}
    </label>
  );
}
const statusText = {
  live: "Activo",
  done: "Completado",
  draft: "Borrador",
  blocked: "Bloqueado",
  danger: "Error",
};
export function StatusDot({
  status = "live",
}: {
  status?: keyof typeof statusText;
}) {
  return <i aria-hidden="true" className={`ui-status-dot dot-${status}`} />;
}
export function Badge({
  status = "live",
  children,
}: {
  status?: keyof typeof statusText;
  children?: ReactNode;
}) {
  return (
    <span className={`ui-badge badge-${status}`}>
      <StatusDot status={status} />
      {children ?? statusText[status]}
    </span>
  );
}

export function DataTable<T>({
  columns,
  data,
  empty = "No hay resultados para mostrar.",
  pageSize = 8,
}: {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  empty?: string;
  pageSize?: number;
}) {
  const [filter, setFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const table = useReactTable({
    data,
    columns,
    state: { globalFilter: filter, sorting, rowSelection },
    onGlobalFilterChange: setFilter,
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
    enableRowSelection: true,
  });
  return (
    <section className="ui-table-wrap">
      <div className="ui-table-tools">
        <label className="ui-search">
          <Search size={14} />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Buscar en la tabla…"
            aria-label="Buscar en la tabla"
          />
          <kbd>/</kbd>
        </label>
        <span className="ui-table-count">
          {table.getFilteredRowModel().rows.length} registros
        </span>
      </div>
      <div className="ui-table-scroll">
        <table className="ui-table">
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th key={header.id}>
                    {header.isPlaceholder ? null : (
                      <button
                        className="ui-sort"
                        aria-label={`Ordenar por ${String(header.column.columnDef.header ?? header.id)}`}
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {header.column.getCanSort() &&
                          (header.column.getIsSorted() === "asc" ? (
                            <ArrowUp size={12} />
                          ) : header.column.getIsSorted() === "desc" ? (
                            <ArrowDown size={12} />
                          ) : (
                            <ChevronsUpDown size={12} />
                          ))}
                      </button>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} data-selected={row.getIsSelected()}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {table.getRowModel().rows.length === 0 && (
          <EmptyState title="Sin coincidencias" description={empty} />
        )}
      </div>
      <div className="ui-table-foot">
        <span>
          {Object.keys(rowSelection).length
            ? `${Object.keys(rowSelection).length} seleccionados · `
            : ""}
          Página {table.getState().pagination.pageIndex + 1} de{" "}
          {Math.max(1, table.getPageCount())}
        </span>
        <div>
          <Button
            variant="outline"
            aria-label="Página anterior"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronLeft size={15} />
          </Button>
          <Button
            variant="outline"
            aria-label="Página siguiente"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            <ChevronRight size={15} />
          </Button>
        </div>
      </div>
    </section>
  );
}

export function Dialog({
  trigger,
  title,
  description,
  children,
}: {
  trigger: ReactNode;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <DialogPrimitive.Root>
      <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ui-overlay" />
        <DialogPrimitive.Content className="ui-dialog">
          <DialogPrimitive.Close
            className="ui-dialog-close"
            aria-label="Cerrar"
          >
            <X size={16} />
          </DialogPrimitive.Close>
          <DialogPrimitive.Title className="ui-dialog-title">
            {title}
          </DialogPrimitive.Title>
          {description && (
            <DialogPrimitive.Description className="ui-dialog-description">
              {description}
            </DialogPrimitive.Description>
          )}
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
export function Drawer({
  trigger,
  title,
  children,
}: {
  trigger: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <DialogPrimitive.Root>
      <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ui-overlay" />
        <DialogPrimitive.Content className="ui-drawer">
          <DialogPrimitive.Close
            className="ui-dialog-close"
            aria-label="Cerrar"
          >
            <X size={16} />
          </DialogPrimitive.Close>
          <DialogPrimitive.Title className="ui-dialog-title">
            {title}
          </DialogPrimitive.Title>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
export const Tabs = TabsPrimitive.Root;
export const TabList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className = "", ...props }, ref) => (
  <TabsPrimitive.List ref={ref} className={`ui-tabs ${className}`} {...props} />
));
TabList.displayName = "TabList";
export const Tab = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className = "", ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={`ui-tab ${className}`}
    {...props}
  />
));
Tab.displayName = "Tab";
export const TabPanel = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className = "", ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={`ui-tab-panel ${className}`}
    {...props}
  />
));
TabPanel.displayName = "TabPanel";
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState("");
  useEffect(() => {
    const handler = (event: Event) =>
      setMessage((event as CustomEvent<string>).detail);
    window.addEventListener("cyberlab:toast", handler);
    return () => window.removeEventListener("cyberlab:toast", handler);
  }, []);
  return (
    <ToastPrimitive.Provider duration={3600}>
      <ToastPrimitive.Root
        className="ui-toast"
        open={!!message}
        onOpenChange={(open) => {
          if (!open) setMessage("");
        }}
      >
        <ToastPrimitive.Title>{message}</ToastPrimitive.Title>
        <ToastPrimitive.Close aria-label="Cerrar aviso">
          <X size={14} />
        </ToastPrimitive.Close>
      </ToastPrimitive.Root>
      <ToastPrimitive.Viewport className="ui-toast-viewport" />
      {children}
    </ToastPrimitive.Provider>
  );
}
export function toast(message: string) {
  window.dispatchEvent(new CustomEvent("cyberlab:toast", { detail: message }));
}
export function Tooltip({
  content,
  children,
}: {
  content: string;
  children: ReactNode;
}) {
  return (
    <TooltipPrimitive.Provider delayDuration={350}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content className="ui-tooltip" sideOffset={6}>
            {content}
            <TooltipPrimitive.Arrow className="ui-tooltip-arrow" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
export function Skeleton({ className = "" }: { className?: string }) {
  return <span className={`ui-skeleton ${className}`} aria-hidden="true" />;
}
export function EmptyState({
  title = "Aún no hay contenido",
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="ui-state">
      <span className="ui-state-mark">
        <Search size={16} />
      </span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function ErrorState({
  title = "No se pudo cargar",
  description = "Revisa la conexión e inténtalo de nuevo.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="ui-state ui-error-state">
      <span className="ui-state-mark">
        <CircleAlert size={16} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  );
}
export function Markdown({ source }: { source: string }) {
  return (
    <article className="ui-markdown">
      <ReactMarkdown>{source}</ReactMarkdown>
    </article>
  );
}

export function CommandPalette({
  open,
  onOpenChange,
  items,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: { label: string; hint?: string; action: () => void }[];
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      items.filter((item) =>
        item.label.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
      ),
    [items, query],
  );
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(!open);
      }
      if (event.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onOpenChange, open]);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ui-overlay" />
        <DialogPrimitive.Content className="ui-command">
          <DialogPrimitive.Title className="sr-only">
            Buscar y navegar
          </DialogPrimitive.Title>
          <label className="ui-command-input">
            <Search size={17} />
            <input
              autoFocus
              placeholder="¿Adónde quieres ir?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <kbd>ESC</kbd>
          </label>
          <div className="ui-command-list">
            {filtered.map((item, i) => (
              <button
                key={item.label}
                onClick={() => {
                  onOpenChange(false);
                  item.action();
                }}
              >
                <Command size={14} />
                <span>{item.label}</span>
                <small>{item.hint ?? `⌘ ${i + 1}`}</small>
              </button>
            ))}
            {filtered.length === 0 && (
              <EmptyState title="No encontramos esa sección" />
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
