"use client";

import { useState, useEffect, useCallback } from "react";
import { listShares, deleteShare, type ShareItem } from "@/lib/api/files";

interface SharesViewProps {
  page: number;
  pageSize: number;
  onError: (msg: string) => void;
  onTotalChange: (total: number) => void;
  reloadKey: number;
}

export default function SharesView({ page, pageSize, onError, onTotalChange, reloadKey }: SharesViewProps) {
  const [shares, setShares] = useState<ShareItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadShares = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listShares((page - 1) * pageSize, pageSize);
      setShares(res.items);
      onTotalChange(res.total);
    } catch (err) {
      onError(err instanceof Error ? err.message : "加载分享失败");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, onError, onTotalChange]);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const res = await listShares((page - 1) * pageSize, pageSize);
        if (!active) return;
        setShares(res.items);
        onTotalChange(res.total);
      } catch (err) {
        if (!active) onError(err instanceof Error ? err.message : "加载分享失败");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [page, pageSize, onError, onTotalChange, reloadKey]);

  async function handleCancelShare(shareId: string) {
    if (!confirm("确定取消此分享吗？")) return;
    try {
      await deleteShare(shareId);
      await loadShares();
    } catch (err) {
      onError(err instanceof Error ? err.message : "取消分享失败");
    }
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
    return <div className="py-20 text-center text-gray-400">加载中...</div>;
  }

  if (shares.length === 0) {
    return (
      <div className="flex flex-col items-center py-20 text-gray-400">
        <div className="text-5xl mb-4">🔗</div>
        <p className="text-base font-medium">暂无分享</p>
        <p className="text-sm mt-1">在全部文件中选中文件后点击「分享」即可创建分享</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-gray-200 text-gray-500">
          <tr>
            <th className="py-3 px-4 text-left font-medium">文件名</th>
            <th className="py-3 px-4 text-left font-medium">提取码</th>
            <th className="py-3 px-4 text-left font-medium">浏览次数</th>
            <th className="py-3 px-4 text-left font-medium">过期时间</th>
            <th className="py-3 px-4 text-left font-medium">创建时间</th>
            <th className="py-3 px-4 text-left font-medium">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {shares.map((share) => (
            <tr key={share.id} className="hover:bg-gray-50">
              <td className="py-3 px-4 text-gray-900">{share.filename}</td>
              <td className="py-3 px-4 font-mono text-blue-600">{share.extract_code}</td>
              <td className="py-3 px-4 text-gray-600">{share.views}</td>
              <td className="py-3 px-4 text-gray-600">
                {share.expires_at ? new Date(share.expires_at).toLocaleString() : "永久有效"}
              </td>
              <td className="py-3 px-4 text-gray-600">
                {new Date(share.created_at).toLocaleString()}
              </td>
              <td className="py-3 px-4">
                <div className="flex gap-2">
                  <button
                    onClick={() => copyShareLink(share.share_token)}
                    className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                  >
                    复制链接
                  </button>
                  <button
                    onClick={() => handleCancelShare(share.id)}
                    className="text-red-600 hover:text-red-700 text-sm font-medium"
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