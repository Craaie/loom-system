/**
 * Job 详情页专属布局
 * 
 * 覆盖根 layout 的 Sidebar + padding 布局，
 * 使任务详情页以全屏模式渲染。
 */
export default function JobLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-screen w-screen overflow-hidden">
      {children}
    </div>
  );
}
