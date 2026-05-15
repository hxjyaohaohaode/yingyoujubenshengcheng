import { useState, useCallback } from 'react'
import { Select, Input, Space, Tag, Button, Popover } from 'antd'
import { FilterOutlined, ClearOutlined, SearchOutlined } from '@ant-design/icons'
import { CharacterFilter } from './plugins/types'

interface FilterBarProps {
  filter: CharacterFilter
  onChange: (filter: CharacterFilter) => void
  viewLabel?: string
}

const ROLE_OPTIONS = [
  { value: 'protagonist', label: '主角', color: '#6366f1' },
  { value: 'antagonist', label: '反派', color: '#ef4444' },
  { value: 'love_interest', label: '女主', color: '#ec4899' },
  { value: 'rival', label: '对手', color: '#f59e0b' },
  { value: 'mentor', label: '导师', color: '#8b5cf6' },
  { value: 'sidekick', label: '伙伴', color: '#10b981' },
  { value: 'supporting', label: '配角', color: '#6b7280' },
  { value: 'cameo', label: '客串', color: '#9ca3af' },
]

const RELATION_OPTIONS = [
  { value: 'friend', label: '朋友', color: '#10b981' },
  { value: 'enemy', label: '敌人', color: '#ef4444' },
  { value: 'lover', label: '恋人', color: '#ec4899' },
  { value: 'family', label: '家人', color: '#f59e0b' },
  { value: 'rival', label: '竞争对手', color: '#f97316' },
  { value: 'mentor', label: '师徒', color: '#8b5cf6' },
  { value: 'ally', label: '盟友', color: '#06b6d4' },
  { value: 'related', label: '关联', color: '#64748b' },
]

export default function FilterBar({ filter, onChange, viewLabel }: FilterBarProps) {
  const [popoverOpen, setPopoverOpen] = useState(false)
  const hasActiveFilters = filter.roleTypes.length > 0 || filter.relationTypes.length > 0 || filter.showOnlyMajor

  const updateFilter = useCallback((patch: Partial<CharacterFilter>) => {
    onChange({ ...filter, ...patch })
  }, [filter, onChange])

  const clearAll = useCallback(() => {
    onChange({ roleTypes: [], relationTypes: [], showOnlyMajor: false, searchText: '' })
  }, [onChange])

  const getRoleColor = (value: string) => ROLE_OPTIONS.find(o => o.value === value)?.color || '#6b7280'

  const filterContent = (
    <div className="space-y-3 w-[280px]">
      <div>
        <div className="text-xs font-medium mb-1 opacity-60">按角色类型</div>
        <Select
          mode="multiple"
          size="small"
          className="w-full"
          placeholder="选择角色类型"
          value={filter.roleTypes}
          onChange={(vals) => updateFilter({ roleTypes: vals })}
          options={ROLE_OPTIONS.map(o => ({
            value: o.value,
            label: (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ background: o.color }} />
                <span>{o.label}</span>
              </span>
            ),
          }))}
        />
      </div>

      <div>
        <div className="text-xs font-medium mb-1 opacity-60">按关系类型</div>
        <Select
          mode="multiple"
          size="small"
          className="w-full"
          placeholder="选择关系类型"
          value={filter.relationTypes}
          onChange={(vals) => updateFilter({ relationTypes: vals })}
          options={RELATION_OPTIONS.map(o => ({
            value: o.value,
            label: (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ background: o.color }} />
                <span>{o.label}</span>
              </span>
            ),
          }))}
        />
      </div>

      <div className="flex items-center justify-between pt-1 border-t border-gray-100 dark:border-slate-700">
        <label className="text-xs opacity-60">仅显示主要角色</label>
        <Button
          size="small"
          type={filter.showOnlyMajor ? 'primary' : 'default'}
          onClick={() => updateFilter({ showOnlyMajor: !filter.showOnlyMajor })}
        >
          {filter.showOnlyMajor ? '已开启' : '关闭'}
        </Button>
      </div>
    </div>
  )

  return (
    <div className="flex items-center gap-2 shrink-0">
      <Space size={4}>
        <Popover
          content={filterContent}
          trigger="click"
          open={popoverOpen}
          onOpenChange={setPopoverOpen}
          placement="bottomLeft"
          title={
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">视图筛选</span>
              {hasActiveFilters && (
                <Button size="small" type="text" danger icon={<ClearOutlined />} onClick={clearAll}>
                  清除
                </Button>
              )}
            </div>
          }
        >
          <Button
            size="small"
            icon={<FilterOutlined />}
            type={hasActiveFilters ? 'primary' : 'default'}
          >
            筛选
            {hasActiveFilters && (
              <span className="ml-1 text-[10px] opacity-80">
                ({filter.roleTypes.length + filter.relationTypes.length + (filter.showOnlyMajor ? 1 : 0)})
              </span>
            )}
          </Button>
        </Popover>

        <Input
          size="small"
          prefix={<SearchOutlined className="opacity-40" />}
          placeholder="搜索节点..."
          className="w-[140px]"
          value={filter.searchText}
          onChange={(e) => updateFilter({ searchText: e.target.value })}
          allowClear
        />

        {hasActiveFilters && (
          <div className="flex items-center gap-1 ml-1">
            {filter.roleTypes.slice(0, 3).map((rt: string) => (
              <Tag key={rt} color={getRoleColor(rt).slice(1)} className="!text-[10px] !m-0">
                {ROLE_OPTIONS.find(o => o.value === rt)?.label || rt}
              </Tag>
            ))}
            {(filter.roleTypes.length > 3 || filter.relationTypes.length > 0) && (
              <span className="text-[10px] opacity-40 ml-1">+{Math.max(0, filter.roleTypes.length - 3) + filter.relationTypes.length}</span>
            )}
          </div>
        )}
      </Space>
    </div>
  )
}