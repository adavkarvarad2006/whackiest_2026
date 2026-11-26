"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

interface AssistantMarkdownProps {
  content: string;
}

function isSafeHref(href?: string): boolean {
  if (!href) return false;
  const trimmed = href.trim().toLowerCase();
  return (
    trimmed.startsWith("https://") ||
    trimmed.startsWith("http://") ||
    trimmed.startsWith("mailto:") ||
    trimmed.startsWith("/") ||
    trimmed.startsWith("#")
  );
}

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mt-4 first:mt-0 mb-2 text-base font-bold tracking-tight text-[#090909] dark:text-neutral-100">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-4 first:mt-0 mb-2 text-[15px] font-semibold tracking-tight text-[#090909] dark:text-neutral-100">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3.5 first:mt-0 mb-1.5 text-sm font-semibold text-[#111111] dark:text-neutral-100">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-3 first:mt-0 mb-1 text-[13px] font-semibold text-[#111111] dark:text-neutral-200">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="my-2 first:mt-0 last:mb-0 text-sm leading-relaxed text-[#111111] dark:text-neutral-100">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-[#090909] dark:text-white">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-[#222222] dark:text-neutral-200">{children}</em>
  ),
  ul: ({ children }) => (
    <ul className="my-2.5 first:mt-0 last:mb-0 list-disc pl-5 space-y-1.5 text-sm leading-relaxed text-[#111111] dark:text-neutral-100 marker:text-[#555555] dark:marker:text-neutral-400">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2.5 first:mt-0 last:mb-0 list-decimal pl-5 space-y-1.5 text-sm leading-relaxed text-[#111111] dark:text-neutral-100 marker:font-medium marker:text-[#555555] dark:marker:text-neutral-400">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-0.5 [&>p]:my-1">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-[#090909] dark:border-neutral-400 pl-3.5 py-0.5 text-[13px] text-[#444444] dark:text-neutral-300 bg-white/70 dark:bg-neutral-800/50 rounded-r-xl">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-[#E8E8E8] dark:border-neutral-700" />,
  a: ({ href, children }) => {
    if (!isSafeHref(href)) {
      return <span className="underline decoration-[#999999]">{children}</span>;
    }
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-[#090909] dark:text-white underline underline-offset-2 decoration-[#888888] hover:decoration-[#090909] dark:hover:decoration-white"
      >
        {children}
      </a>
    );
  },
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-2xl border border-[#E8E8E8] dark:border-neutral-700 bg-white dark:bg-neutral-900">
      <table className="w-full min-w-[360px] border-collapse text-left text-xs tabular-nums">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-[#F3F3F3] dark:bg-neutral-800 border-b border-[#E8E8E8] dark:border-neutral-700 text-[#111111] dark:text-neutral-100">
      {children}
    </thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-[#EFEFEF] dark:divide-neutral-800 text-[#222222] dark:text-neutral-200">
      {children}
    </tbody>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-[#FAFAFA] dark:hover:bg-neutral-800/50 transition-colors">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-3.5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-[#444444] dark:text-neutral-300 whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3.5 py-2.5 text-xs leading-snug align-top">{children}</td>
  ),
  pre: ({ children }) => (
    <div className="my-3 overflow-hidden rounded-2xl border border-[#222222] dark:border-neutral-700 bg-[#0F1115]">
      <pre className="overflow-x-auto p-3.5 text-xs leading-relaxed font-mono text-neutral-100 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-xs [&_code]:font-mono [&_code]:text-inherit">
        {children}
      </pre>
    </div>
  ),
  code: ({ className, children, ...props }) => {
    const isCodeBlock = Boolean(
      className?.includes("language-") ||
        className?.includes("hljs") ||
        String(children).includes("\n")
    );
    if (isCodeBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded-md border border-[#E5E5E5] dark:border-neutral-700 bg-[#EEEEEE] dark:bg-neutral-800 px-1.5 py-0.5 text-[12px] font-mono text-[#111111] dark:text-neutral-100"
        {...props}
      >
        {children}
      </code>
    );
  },
};

export function AssistantMarkdown({ content }: AssistantMarkdownProps) {
  return (
    <div className="arthalens-md space-y-1 break-words">
      <ReactMarkdown
        remarkPlugins={[[remarkGfm, { singleTilde: false }]]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
