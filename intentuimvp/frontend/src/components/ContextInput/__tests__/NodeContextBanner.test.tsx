import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NodeContextBanner } from '../NodeContextBanner';
import type { ConversationScope } from '@/state/conversationStore';

describe('NodeContextBanner', () => {
  it('should not render when scope is global', () => {
    const scope: ConversationScope = { type: 'global' };
    
    const { container } = render(
      <NodeContextBanner scope={scope} />
    );
    
    expect(container.querySelector('.node-context-banner')).toBeNull();
  });

  it('should not render when visible is false', () => {
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: true,
    };
    
    const { container } = render(
      <NodeContextBanner scope={scope} visible={false} />
    );
    
    expect(container.querySelector('.node-context-banner')).toBeNull();
  });

  it('should render node title when scope is node', () => {
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: true,
    };
    
    render(<NodeContextBanner scope={scope} />);
    
    expect(screen.getByText('Test Node')).toBeInTheDocument();
    expect(screen.getByText('Context:')).toBeInTheDocument();
  });

  it('should show content badge when hasContent is true', () => {
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: true,
    };
    
    render(<NodeContextBanner scope={scope} />);
    
    expect(screen.getByText('Content active')).toBeInTheDocument();
  });

  it('should not show content badge when hasContent is false', () => {
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: false,
    };
    
    render(<NodeContextBanner scope={scope} />);
    
    expect(screen.queryByText('Content active')).not.toBeInTheDocument();
  });

  it('should truncate long titles', () => {
    const longTitle = 'This is a very long node title that should be truncated to fit the display';
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: longTitle,
      hasContent: false,
    };
    
    render(<NodeContextBanner scope={scope} />);
    
    const titleElement = screen.getByTitle(longTitle);
    expect(titleElement.textContent).toContain('...');
    expect(titleElement.textContent?.length).toBeLessThan(longTitle.length);
  });

  it('should call onClearContext when clear button is clicked', () => {
    const onClearContext = vi.fn();
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: true,
    };
    
    render(<NodeContextBanner scope={scope} onClearContext={onClearContext} />);
    
    const clearButton = screen.getByRole('button', { name: /clear node context/i });
    fireEvent.click(clearButton);
    
    expect(onClearContext).toHaveBeenCalledTimes(1);
  });

  it('should not render clear button when onClearContext is not provided', () => {
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: true,
    };
    
    render(<NodeContextBanner scope={scope} />);
    
    expect(screen.queryByRole('button', { name: /clear node context/i })).not.toBeInTheDocument();
  });

  it('should have proper accessibility attributes', () => {
    const scope: ConversationScope = {
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: true,
    };
    
    render(<NodeContextBanner scope={scope} />);
    
    const banner = screen.getByRole('status');
    expect(banner).toHaveAttribute('aria-live', 'polite');
    expect(banner).toHaveAttribute('aria-label', 'Conversation context: Test Node');
  });
});
