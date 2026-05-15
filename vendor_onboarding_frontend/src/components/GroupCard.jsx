export default function GroupCard({ icon, title, count, children }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 bg-gray-50 border-b border-gray-100">
        <span className="text-xl">{icon}</span>
        <span className="font-semibold text-sm text-gray-800 flex-1">{title}</span>
        <span className="text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">{count}</span>
      </div>
      <div className="p-5 space-y-4">{children}</div>
    </div>
  )
}
