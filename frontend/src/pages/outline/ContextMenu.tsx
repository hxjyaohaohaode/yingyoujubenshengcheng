import { useEffect, useRef } from 'react'
import type { Node, Edge } from '@xyflow/react'

interface ContextMenuProps {
  x: number
  y: number
  nodes: Node[]
  edges: Edge[]
  onClose: () => void
  onDeleteNodes: (ids: string[]) => void
  onDeleteEdge: (id: string) => void
  onEditEdge: (edge: Edge) => void
  onDuplicateNode: (node: Node) => void
  onAddNode: (type: string, x: number, y: number) => void
  onAlignNodes: (direction: 'horizontal' | 'vertical') => void
  onSetArcType: (arcType: string) => void
}

export default function ContextMenu({
  x, y, nodes, edges, onClose,
  onDeleteNodes, onDeleteEdge, onEditEdge, onDuplicateNode,
  onAddNode, onAlignNodes, onSetArcType,
}: ContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as HTMLElement)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const isNodeMenu = nodes.length > 0
  const isEdgeMenu = edges.length > 0 && nodes.length === 0
  const isPaneMenu = nodes.length === 0 && edges.length === 0
  const isMultiple = nodes.length > 1
  const allSameType = isNodeMenu && new Set(nodes.map((n) => n.type)).size === 1

  const mi: React.CSSProperties = {
    padding: '5px 12px', fontSize: 11, cursor: 'pointer',
    color: '#333', borderRadius: 3, transition: 'background 0.1s',
  }
  const sep: React.CSSProperties = { height: 1, background: '#f0f0f0', margin: '3px 0' }

  return (
    <div ref={ref} style={{
      position: 'fixed', left: x, top: y, zIndex: 1000,
      background: '#fff', borderRadius: 8, padding: '4px 0',
      boxShadow: '0 6px 20px rgba(0,0,0,0.15)', minWidth: 160,
      border: '1px solid #e8e8e8',
    }}
      onClick={(e) => e.stopPropagation()}
    >
      {isNodeMenu && (
        <>
          <div style={mi} onClick={() => { nodes.forEach((n) => onDuplicateNode(n)); onClose() }}>
            📋 复制{isMultiple ? ` (${nodes.length}个)` : ''}
          </div>
          <div style={mi} onClick={() => { onDeleteNodes(nodes.map((n) => n.id)); onClose() }}
            onMouseEnter={(e) => { (e.target as HTMLElement).style.background = '#fff1f0'; (e.target as HTMLElement).style.color = '#ff4d4f' }}
            onMouseLeave={(e) => { (e.target as HTMLElement).style.background = ''; (e.target as HTMLElement).style.color = '#333' }}>
            🗑️ 删除{isMultiple ? ` (${nodes.length}个)` : ''}
          </div>
          <div style={sep} />
          {isMultiple && (
            <>
              <div style={{ padding: '3px 12px', fontSize: 9, color: '#999', fontWeight: 600 }}>对齐</div>
              <div style={mi} onClick={() => { onAlignNodes('horizontal'); onClose() }}>⬛ 水平对齐</div>
              <div style={mi} onClick={() => { onAlignNodes('vertical'); onClose() }}>⬛ 垂直对齐</div>
              <div style={sep} />
            </>
          )}
          {allSameType && (nodes[0].type === 'story_arc' || nodes[0].type === 'chapter') && (
            <>
              <div style={{ padding: '3px 12px', fontSize: 9, color: '#999', fontWeight: 600 }}>弧线类型</div>
              <div style={mi} onClick={() => { onSetArcType('main'); onClose() }}>🔵 设为主线</div>
              <div style={mi} onClick={() => { onSetArcType('sub'); onClose() }}>🟠 设为支线</div>
              <div style={sep} />
            </>
          )}
        </>
      )}

      {isEdgeMenu && (
        <>
          <div style={mi} onClick={() => { onEditEdge(edges[0]); onClose() }}>✏️ 编辑连线</div>
          <div style={mi} onClick={() => { onDeleteEdge(edges[0].id); onClose() }}
            onMouseEnter={(e) => { (e.target as HTMLElement).style.background = '#fff1f0'; (e.target as HTMLElement).style.color = '#ff4d4f' }}
            onMouseLeave={(e) => { (e.target as HTMLElement).style.background = ''; (e.target as HTMLElement).style.color = '#333' }}>
            🗑️ 删除连线
          </div>
          <div style={sep} />
        </>
      )}

      {isPaneMenu && (
        <>
          <div style={{ padding: '3px 12px', fontSize: 9, color: '#999', fontWeight: 600 }}>新建节点</div>
          <div style={mi} onClick={() => { onAddNode('story_arc', x, y); onClose() }}>🔵 故事线</div>
          <div style={mi} onClick={() => { onAddNode('chapter', x, y); onClose() }}>🟢 章节</div>
          <div style={mi} onClick={() => { onAddNode('event', x, y); onClose() }}>🟠 事件</div>
          <div style={mi} onClick={() => { onAddNode('choice', x, y); onClose() }}>🟣 抉择</div>
          <div style={sep} />
        </>
      )}

      <div style={mi} onClick={onClose}>✕ 关闭菜单</div>
    </div>
  )
}
