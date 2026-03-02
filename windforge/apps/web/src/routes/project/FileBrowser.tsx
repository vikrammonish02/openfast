import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { filesApi } from '@/api/client';
import type { FileNode } from '@/types';
import {
  FolderOpen,
  FolderClosed,
  FileText,
  ChevronRight,
  ChevronDown,
  Copy,
  Download,
  RefreshCw,
  Loader2,
  FileCode2,
} from 'lucide-react';
import clsx from 'clsx';
import toast from 'react-hot-toast';

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / Math.pow(1024, i);
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

// Count total files in a tree
function countFiles(nodes: FileNode[]): number {
  let count = 0;
  for (const node of nodes) {
    if (node.is_dir && node.children) {
      count += countFiles(node.children);
    } else if (!node.is_dir) {
      count++;
    }
  }
  return count;
}

interface TreeNodeProps {
  node: FileNode;
  depth: number;
  selectedPath: string | null;
  onSelect: (node: FileNode) => void;
  expandedDirs: Set<string>;
  onToggleDir: (path: string) => void;
}

function TreeNode({ node, depth, selectedPath, onSelect, expandedDirs, onToggleDir }: TreeNodeProps) {
  const isExpanded = expandedDirs.has(node.path);
  const isSelected = selectedPath === node.path;

  if (node.is_dir) {
    return (
      <div>
        <button
          onClick={() => onToggleDir(node.path)}
          className={clsx(
            'w-full flex items-center gap-1.5 px-2 py-1.5 text-sm hover:bg-surface-dark-tertiary rounded transition-colors',
            isSelected ? 'bg-accent-950/40 text-accent-400' : 'text-slate-300',
          )}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-slate-500 flex-shrink-0" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-slate-500 flex-shrink-0" />
          )}
          {isExpanded ? (
            <FolderOpen className="h-4 w-4 text-accent-400 flex-shrink-0" />
          ) : (
            <FolderClosed className="h-4 w-4 text-slate-400 flex-shrink-0" />
          )}
          <span className="truncate font-medium">{node.name}</span>
          {node.children && (
            <span className="ml-auto text-xs text-slate-500">{countFiles([node])}</span>
          )}
        </button>
        {isExpanded && node.children && (
          <div>
            {node.children.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedPath={selectedPath}
                onSelect={onSelect}
                expandedDirs={expandedDirs}
                onToggleDir={onToggleDir}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // File extension coloring
  const ext = node.name.split('.').pop()?.toLowerCase();
  const extColor = ext === 'fst' ? 'text-green-400' : ext === 'dat' ? 'text-blue-400' : ext === 'inp' ? 'text-yellow-400' : 'text-slate-400';

  return (
    <button
      onClick={() => onSelect(node)}
      className={clsx(
        'w-full flex items-center gap-1.5 px-2 py-1.5 text-sm hover:bg-surface-dark-tertiary rounded transition-colors',
        isSelected ? 'bg-accent-950/40 text-accent-400' : 'text-slate-200',
      )}
      style={{ paddingLeft: `${depth * 16 + 8 + 18}px` }}
    >
      <FileText className={clsx('h-4 w-4 flex-shrink-0', extColor)} />
      <span className="truncate">{node.name}</span>
      <span className="ml-auto text-xs text-slate-500">{formatSize(node.size)}</span>
    </button>
  );
}

export default function FileBrowser() {
  const { projectId } = useParams<{ projectId: string }>();
  const [tree, setTree] = useState<FileNode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isLoadingContent, setIsLoadingContent] = useState(false);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());

  const loadTree = useCallback(async () => {
    if (!projectId) return;
    setIsLoading(true);
    try {
      const data = await filesApi.listFiles(projectId);
      setTree(data);
      // Auto-expand first two levels
      const toExpand = new Set<string>();
      for (const node of data) {
        if (node.is_dir) {
          toExpand.add(node.path);
          if (node.children) {
            for (const child of node.children) {
              if (child.is_dir) {
                toExpand.add(child.path);
                if (child.children) {
                  for (const grandchild of child.children) {
                    if (grandchild.is_dir) toExpand.add(grandchild.path);
                  }
                }
              }
            }
          }
        }
      }
      setExpandedDirs(toExpand);
    } catch {
      // No files yet - that's OK
      setTree([]);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadTree();
  }, [loadTree]);

  const handleSelectFile = async (node: FileNode) => {
    if (node.is_dir) return;
    setSelectedFile(node);
    setIsLoadingContent(true);
    try {
      const content = await filesApi.getFileContent(projectId!, node.path);
      setFileContent(content);
    } catch {
      setFileContent('Error loading file content');
      toast.error('Failed to load file');
    } finally {
      setIsLoadingContent(false);
    }
  };

  const handleToggleDir = (path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleCopy = async () => {
    if (fileContent) {
      await navigator.clipboard.writeText(fileContent);
      toast.success('Copied to clipboard');
    }
  };

  const handleDownload = () => {
    if (selectedFile && projectId) {
      const url = filesApi.getDownloadUrl(projectId, selectedFile.path);
      window.open(url, '_blank');
    }
  };

  const totalFiles = countFiles(tree);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Project Files</h2>
          <p className="text-sm text-slate-400">
            {totalFiles > 0
              ? `${totalFiles} generated OpenFAST input file${totalFiles !== 1 ? 's' : ''}`
              : 'Generated input files will appear here after running a simulation'}
          </p>
        </div>
        <button
          onClick={loadTree}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-200 bg-surface-dark-tertiary rounded-lg hover:bg-slate-600 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {tree.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-600 py-16">
          <FileCode2 className="h-12 w-12 text-slate-300 mb-3" />
          <h3 className="text-base font-semibold text-slate-200">No files generated yet</h3>
          <p className="mt-1 text-sm text-slate-400 max-w-sm text-center">
            Go to the Simulate tab and start a simulation to generate OpenFAST input files.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-280px)]">
          {/* File Tree */}
          <div className="rounded-xl border border-slate-600 bg-surface-dark-secondary overflow-hidden flex flex-col">
            <div className="px-4 py-3 border-b border-slate-700 bg-surface-dark-tertiary">
              <h3 className="text-sm font-semibold text-slate-200">File Tree</h3>
            </div>
            <div className="flex-1 overflow-auto p-2">
              {tree.map((node) => (
                <TreeNode
                  key={node.path}
                  node={node}
                  depth={0}
                  selectedPath={selectedFile?.path || null}
                  onSelect={handleSelectFile}
                  expandedDirs={expandedDirs}
                  onToggleDir={handleToggleDir}
                />
              ))}
            </div>
          </div>

          {/* File Content Viewer */}
          <div className="lg:col-span-2 rounded-xl border border-slate-600 bg-surface-dark-secondary overflow-hidden flex flex-col">
            {selectedFile ? (
              <>
                <div className="px-4 py-3 border-b border-slate-700 bg-surface-dark-tertiary flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-accent-400" />
                    <span className="text-sm font-semibold text-slate-200">{selectedFile.name}</span>
                    <span className="text-xs text-slate-500">{formatSize(selectedFile.size)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleCopy}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-200 bg-surface-dark-secondary rounded-lg hover:bg-slate-600 border border-slate-600 transition-colors"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      Copy
                    </button>
                    <button
                      onClick={handleDownload}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-200 bg-surface-dark-secondary rounded-lg hover:bg-slate-600 border border-slate-600 transition-colors"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Download
                    </button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto">
                  {isLoadingContent ? (
                    <div className="flex items-center justify-center py-16">
                      <Loader2 className="h-6 w-6 animate-spin text-accent-500" />
                    </div>
                  ) : (
                    <pre className="p-4 text-xs font-mono text-slate-200 leading-relaxed whitespace-pre">
                      {fileContent?.split('\n').map((line, i) => (
                        <div key={i} className="flex hover:bg-surface-dark-tertiary">
                          <span className="inline-block w-10 text-right pr-4 text-slate-500 select-none flex-shrink-0">
                            {i + 1}
                          </span>
                          <span className="flex-1">{line}</span>
                        </div>
                      ))}
                    </pre>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <FileText className="h-12 w-12 text-slate-500 mx-auto mb-3" />
                  <p className="text-sm text-slate-400">Select a file to view its contents</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
