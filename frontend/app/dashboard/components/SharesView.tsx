"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listShares, deleteShare, type ShareItem } from "@/lib/api/files";
import { queryKeys } from "@/lib/query/keys";

interface SharesViewProps {
  page: number;
  pageSize: number;
  onError: (msg: string) => void;
  onTotalChange: (total: number) => void;
  reloadKey: number;
}

export default function SharesView({ page, pageSize, onError, onTotalChange, reloadKey }: SharesViewProps) {
  const queryClient = useQueryClient();

  const { data: shares = [], isLoading: loading } = useQuery({
    queryKey: [...queryKeys.shares.list(page, pageSize), reloadKey],
    queryFn: async () => {
      const res = await listShares((page - 1) * pageSize, pageSize);
      onTotalChange(res.total);
      return res.items;
    },
  });

  const cancelMutation = useMutation({
    mutationFn: deleteShare,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.shares.all });
    },
    onError: (err) => onError(err instanceof Error ? err.message : "取消分享失败"),
  });

  function handleCancelShare(shareId: string) {
    if (!confirm("确定取消此分享吗？")) return;
    cancelMutation.mutate(shareId);
  }

  function copyShareLink(token: string) {
    const url = `${window.location.origin}/share/${token}`;
    navigator.clipboard.writeText(url).then(() => {
      alert("分享链接已复制到剪贴板");
    }).catch(() => {
      prompt("请手动复制分享链接：", url);
    });
  }

  if (loading) {
    return <div className="py-20 text-center text-ink-4">加载中...</div>;
  }

  if (shares.length === 0) {
    return (
      <div className="flex flex-col items-center py-20 text-ink-4">
        <div className="text-5xl mb-4 opacity-50">🔗</div>
        <p className="text-base font-medium text-ink-2">暂无分享</p>
        <p className="text-sm mt-1">在全部文件中选中文件后点击「分享」即可创建分享</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-line bg-surface-2 text-ink-3">
          <tr>
            <th className="py-3 px-4 text-left font-medium">文件名</th>
            <th className="py-3 px-4 text-left font-medium">提取码</th>
            <th className="py-3 px-4 text-left font-medium">浏览次数</th>
            <th className="py-3 px-4 text-left font-medium">过期时间</th>
            <th className="py-3 px-4 text-left font-medium">创建时间</th>
            <th className="py-3 px-4 text-left font-medium">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {shares.map((share) => (
            <tr key={share.id} className="transition-colors hover:bg-surface-2">
              <td className="py-3 px-4 text-ink">{share.filename}</td>
              <td className="py-3 px-4 font-mono text-brand">{share.extract_code}</td>
              <td className="py-3 px-4 text-ink-2 tabular-nums">{share.views}</td>
              <td className="py-3 px-4 text-ink-2 tabular-nums">
                {share.expires_at ? new Date(share.expires_at).toLocaleString() : "永久有效"}
              </td>
              <td className="py-3 px-4 text-ink-2 tabular-nums">
                {new Date(share.created_at).toLocaleString()}
              </td>
              <td className="py-3 px-4">
                <div className="flex gap-2">
                  <button
                    onClick={() => copyShareLink(share.share_token)}
                    className="text-brand hover:text-brand-hover text-sm font-medium transition-colors"
                  >
                    复制链接
                  </button>
                  <button
                    onClick={() => handleCancelShare(share.id)}
                    className="text-danger hover:opacity-80 text-sm font-medium transition-opacity"
                  >
                    取消分享
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}