import { useState } from 'react'
import Card from '@/components/common/Card'

export default function UserCenter() {
  const [email, setEmail] = useState('')
  const [saved, setSaved] = useState(false)

  // Subscription toggles (local state — backend notification module not yet implemented)
  const [subs, setSubs] = useState({
    signal_wechat: false,
    signal_email: false,
    research_wechat: false,
    research_email: false,
    weekly_email: false,
  })

  const [signalFreq, setSignalFreq] = useState<'realtime' | 'daily'>('daily')
  const [researchFreq, setResearchFreq] = useState<'realtime' | 'daily'>('daily')

  const toggleSub = (key: keyof typeof subs) => {
    setSubs((prev) => ({ ...prev, [key]: !prev[key] }))
    setSaved(false)
  }

  const handleSave = () => {
    // TODO: call notification API when backend is ready
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-xl font-bold">用户中心</h2>

      {/* Account info */}
      <Card title="账户信息">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-500 block mb-1">邮箱地址</label>
            <input
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setSaved(false) }}
              placeholder="your@email.com"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">微信绑定</label>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-400">未绑定</span>
              <button className="px-3 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors">
                绑定微信
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* Signal subscription */}
      <Card title="交易信号推送">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-900">微信推送</div>
              <div className="text-xs text-gray-400">通过微信公众号接收信号通知</div>
            </div>
            <ToggleSwitch checked={subs.signal_wechat} onChange={() => toggleSub('signal_wechat')} />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-900">邮件推送</div>
              <div className="text-xs text-gray-400">通过邮件接收信号通知</div>
            </div>
            <ToggleSwitch checked={subs.signal_email} onChange={() => toggleSub('signal_email')} />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-2">推送频率</label>
            <div className="flex gap-2">
              <FreqButton label="实时" active={signalFreq === 'realtime'} onClick={() => setSignalFreq('realtime')} />
              <FreqButton label="每日汇总" active={signalFreq === 'daily'} onClick={() => setSignalFreq('daily')} />
            </div>
          </div>
        </div>
      </Card>

      {/* Research subscription */}
      <Card title="研报推送">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-900">微信推送</div>
              <div className="text-xs text-gray-400">重要研报摘要推送</div>
            </div>
            <ToggleSwitch checked={subs.research_wechat} onChange={() => toggleSub('research_wechat')} />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-900">邮件推送</div>
              <div className="text-xs text-gray-400">研报全文及AI分析推送</div>
            </div>
            <ToggleSwitch checked={subs.research_email} onChange={() => toggleSub('research_email')} />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-2">推送频率</label>
            <div className="flex gap-2">
              <FreqButton label="实时" active={researchFreq === 'realtime'} onClick={() => setResearchFreq('realtime')} />
              <FreqButton label="每日汇总" active={researchFreq === 'daily'} onClick={() => setResearchFreq('daily')} />
            </div>
          </div>
        </div>
      </Card>

      {/* Weekly report */}
      <Card title="周报推送">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-900">策略表现周报</div>
            <div className="text-xs text-gray-400">每周日发送策略运行汇总与收益统计</div>
          </div>
          <ToggleSwitch checked={subs.weekly_email} onChange={() => toggleSub('weekly_email')} />
        </div>
      </Card>

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          className="px-6 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
        >
          保存设置
        </button>
        {saved && <span className="text-sm text-rise">已保存</span>}
        <span className="text-xs text-gray-400 ml-auto">通知模块开发中，设置将在后端就绪后生效</span>
      </div>
    </div>
  )
}

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={`relative w-11 h-6 rounded-full transition-colors ${checked ? 'bg-primary' : 'bg-gray-200'}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

function FreqButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-gray-200 text-gray-500 hover:bg-gray-50'
      }`}
    >
      {label}
    </button>
  )
}
