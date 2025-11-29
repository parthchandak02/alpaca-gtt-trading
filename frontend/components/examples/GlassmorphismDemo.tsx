'use client';

import { GlassCard, GlassContainer, GlassButton, GlassInput } from '@/components/glass';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

/**
 * Demo component showing various glassmorphism patterns
 * Use this as a reference for implementing glass effects
 */
export function GlassmorphismDemo() {
  return (
    <div className="space-y-8 p-8">
      <h1 className="text-3xl font-bold mb-8">Glassmorphism Examples</h1>

      {/* Basic Glass Card */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Basic Glass Card</h2>
        <GlassCard className="p-6">
          <h3 className="text-lg font-medium mb-2">Card Title</h3>
          <p className="text-text-secondary">
            This is a basic glass card with hover effects. It automatically includes
            backdrop blur, transparency, and smooth transitions.
          </p>
        </GlassCard>
      </section>

      {/* Glass Variants */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Glass Variants</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <GlassContainer variant="light" className="p-4">
            <h3 className="font-medium mb-2">Light</h3>
            <p className="text-sm text-text-secondary">Subtle effect</p>
          </GlassContainer>
          <GlassContainer variant="medium" className="p-4">
            <h3 className="font-medium mb-2">Medium</h3>
            <p className="text-sm text-text-secondary">Standard effect</p>
          </GlassContainer>
          <GlassContainer variant="heavy" className="p-4">
            <h3 className="font-medium mb-2">Heavy</h3>
            <p className="text-sm text-sm text-text-secondary">Strong effect</p>
          </GlassContainer>
        </div>
      </section>

      {/* Tinted Glass */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Tinted Glass</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <GlassContainer tint="blue" className="p-4">
            <h3 className="font-medium mb-2">Blue Tint</h3>
            <p className="text-sm text-text-secondary">For info/primary content</p>
          </GlassContainer>
          <GlassContainer tint="purple" className="p-4">
            <h3 className="font-medium mb-2">Purple Tint</h3>
            <p className="text-sm text-text-secondary">For stock/ETF content</p>
          </GlassContainer>
          <GlassContainer tint="green" className="p-4">
            <h3 className="font-medium mb-2">Green Tint</h3>
            <p className="text-sm text-text-secondary">For success/cash content</p>
          </GlassContainer>
        </div>
      </section>

      {/* Form Elements */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Form Elements</h2>
        <GlassCard className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Glass Input</label>
            <GlassInput placeholder="Enter text..." />
          </div>
          <div className="flex gap-2">
            <GlassButton>Glass Button</GlassButton>
            <Button variant="glass">shadcn Glass Button</Button>
          </div>
        </GlassCard>
      </section>

      {/* Badges */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Badges</h2>
        <div className="flex flex-wrap gap-2">
          <Badge>Default</Badge>
          <Badge variant="secondary">Secondary</Badge>
          <Badge variant="success">Success</Badge>
          <Badge variant="warning">Warning</Badge>
          <Badge variant="destructive">Error</Badge>
        </div>
      </section>

      {/* shadcn/ui Components */}
      <section>
        <h2 className="text-xl font-semibold mb-4">shadcn/ui Components</h2>
        <Card className="p-6">
          <CardHeader>
            <CardTitle>Pre-styled Card</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-text-secondary">
              All shadcn/ui components are pre-configured with glassmorphism.
              Just use them normally!
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

