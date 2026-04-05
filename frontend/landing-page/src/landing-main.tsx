"use client";

import { ReactNode } from "react";
import { FileText, RefreshCw, Search, CheckCircle2 } from "lucide-react";

// --- Components ---

const Button = ({
    children,
    variant = 'primary',
    className = '',
    onClick,
    href
}: {
    children: ReactNode;
    variant?: 'primary' | 'secondary' | 'tertiary';
    className?: string;
    onClick?: () => void;
    href?: string;
}) => {
    const baseStyles = "px-7 py-3 rounded-full font-medium transition-all duration-300 flex items-center justify-center gap-2";
    const variants = {
        primary: "bg-terracotta text-white hover:opacity-90",
        secondary: "bg-charcoal text-white hover:opacity-90",
        tertiary: "text-charcoal hover:translate-x-1",
    };

    const classes = `${baseStyles} ${variants[variant]} ${className}`;

    if (href) {
        return (
            <a href={href} className={classes}>
                {children}
            </a>
        );
    }

    return (
        <button
            onClick={onClick}
            className={classes}
        >
            {children}
        </button>
    );
};

const Navbar = () => {
    const scrollTo = (id: string) => {
        const element = document.getElementById(id);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth' });
        } else {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };

    const navItemStyles = "relative transition-all duration-300 hover:text-charcoal hover:scale-110 hover:font-bold cursor-pointer group pb-1";
    const underlineStyles = "absolute bottom-0 left-0 w-0 h-0.5 bg-terracotta/40 transition-all duration-300 group-hover:w-full";

    return (
        <nav className="glass-header sticky top-0 z-50 border-b border-charcoal/5">
            <div className="max-w-7xl mx-auto h-[4.5rem] md:h-20 px-5 md:px-6 flex items-center justify-between">
                <div className="flex items-center gap-8 md:gap-12">
                    <button
                        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                        className="relative h-12 w-[8.5rem] overflow-hidden md:h-14 md:w-[10rem]"
                        aria-label="PolicyDiff"
                    >
                        <img
                            src="/logo.webp"
                            alt="PolicyDiff"
                            className="h-full w-full origin-left scale-[2.35] object-contain object-left"
                        />
                    </button>
                    <div className="hidden md:flex items-center gap-7 text-sm font-medium text-charcoal/60">
                        <button
                            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                            className={navItemStyles}
                        >
                            Platform
                            <div className={underlineStyles} />
                        </button>
                        <button
                            onClick={() => scrollTo('insights')}
                            className={navItemStyles}
                        >
                            Features
                            <div className={underlineStyles} />
                        </button>
                        <button
                            onClick={() => scrollTo('methodology')}
                            className={navItemStyles}
                        >
                            Methodology
                            <div className={underlineStyles} />
                        </button>
                    </div>
                </div>
                <div className="flex items-center gap-2 md:gap-4">
                    <Button variant="tertiary" className="text-sm py-2 px-4" href="/auth/login?returnTo=/">Sign In</Button>
                    <Button variant="primary" className="text-sm py-2 px-6" href="/auth/login?screen_hint=signup&returnTo=/">Get Started</Button>
                </div>
            </div>
        </nav>
    );
};

const FeatureCard = ({ icon: Icon, title, description }: { icon: any, title: string, description: string }) => (
    <div className="flex max-w-sm flex-col gap-4">
        <div className="w-10 h-10 rounded-full bg-[#E8E7E4] flex items-center justify-center text-terracotta/60">
            <Icon size={20} />
        </div>
        <h3 className="text-[1.75rem] leading-tight font-medium">{title}</h3>
        <p className="text-lg text-charcoal/60 leading-relaxed">
            {description}
        </p>
    </div>
);

const Separator = () => (
    <div className="w-full px-6">
        <div className="max-w-7xl mx-auto h-px bg-gradient-to-r from-transparent via-charcoal/10 to-transparent" />
    </div>
);

const SectionLabel = ({ children, className = "" }: { children: ReactNode, className?: string }) => (
    <span className={`inline-block px-3 py-1 rounded-full text-[10px] uppercase tracking-widest font-bold mb-4 ${className}`}>
        {children}
    </span>
);

export default function App() {
    return (
        <div className="min-h-screen bg-alabaster text-charcoal font-sans selection:bg-terracotta/10 selection:text-terracotta">
            <Navbar />

            {/* Hero Section */}
            <section className="relative isolate z-0 overflow-hidden px-5 pt-[4.5rem] pb-24 md:px-6 md:pt-[5.5rem] md:pb-28">
                <div className="relative z-10 mx-auto mb-14 max-w-4xl text-center md:mb-16">
                    <h1 className="mb-6 font-serif text-6xl leading-[1.06] font-medium md:mb-8 md:text-8xl">
                        Stop reading policy PDFs. <br />
                        <span className="italic">Start acting on data.</span>
                    </h1>
                    <p className="mx-auto mb-0 max-w-2xl text-xl leading-relaxed text-charcoal/60 md:text-2xl">
                        PolicyDiff is a purpose-built medical benefit drug intelligence engine.
                        We turn 30-page payer PDFs into structured, comparable, and actionable insights in seconds.
                    </p>
                </div>

                {/* Hero Image Container */}
                <div className="pointer-events-none relative z-10 mx-auto max-w-6xl">
                    <div className="flex aspect-[16/10] items-center justify-center overflow-hidden rounded-[1.75rem] bg-[#e89a74] p-5 md:rounded-[2rem] md:p-10 lg:p-14">
                        <div className="w-full h-full bg-white rounded-xl shadow-2xl overflow-hidden editorial-shadow">
                            {/* Mock App UI */}
                            <div className="w-full h-12 bg-surface-low border-b border-charcoal/5 flex items-center px-4 gap-2">
                                <div className="w-3 h-3 rounded-full bg-terracotta/20" />
                                <div className="w-3 h-3 rounded-full bg-terracotta/20" />
                                <div className="w-3 h-3 rounded-full bg-terracotta/20" />
                            </div>
                            <div className="h-[calc(100%-3rem)] bg-white">
                                <img
                                    src="/dashboard.webp"
                                    alt="PolicyDiff landing page dashboard preview"
                                    className="h-full w-full object-cover object-top"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <Separator />

            {/* Features Grid */}
            <section id="how-it-works" className="bg-surface-low/30 px-5 py-24 scroll-mt-24 md:px-6 md:py-28">
                <div className="max-w-7xl mx-auto">
                    <div className="mb-12 md:mb-14">
                        <SectionLabel className="bg-terracotta/10 text-terracotta">The Problem</SectionLabel>
                        <h2 className="font-serif text-5xl md:text-6xl font-medium leading-tight">
                            Why policy research <br /> is broken today.
                        </h2>
                    </div>
                </div>
                <div className="grid max-w-7xl gap-12 md:grid-cols-3 md:gap-16 lg:gap-20 mx-auto">
                    <FeatureCard
                        icon={FileText}
                        title="Manual PDF Parsing"
                        description="Consultants spend hours reading complex medical benefit PDFs. We automate the extraction of clinical criteria and prior authorization rules."
                    />
                    <FeatureCard
                        icon={RefreshCw}
                        title="Missed Updates"
                        description="Policies change mid-quarter without notice. Patients lose coverage while you're still working from last month's manual spreadsheet."
                    />
                    <FeatureCard
                        icon={Search}
                        title="No Cross-Payer Visibility"
                        description="Knowing what one payer requires isn't enough. PolicyDiff maps coverage criteria across every payer in your portfolio so you can spot differences at a glance."
                    />
                </div>
            </section>


            <Separator />

            {/* Alternating Sections */}
            <section className="px-5 py-24 md:px-6 md:py-28">
                <div className="max-w-7xl mx-auto flex flex-col gap-28 md:gap-32">

                    {/* Section 1 */}
                    <div id="insights" className="grid items-center gap-10 scroll-mt-25 md:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)] md:gap-12 lg:gap-16">
                        <div className="max-w-lg">
                            <SectionLabel className="bg-[#D8E2CF] text-[#4A5D45]">Efficiency</SectionLabel>
                            <h2 className="font-serif text-5xl md:text-6xl font-medium mb-6 md:mb-8 leading-tight">
                                Cross-Payer <br /> Comparison
                            </h2>
                            <p className="text-xl text-charcoal/60 leading-relaxed mb-8 md:mb-10">
                                Visualize coverage landscapes across multiple payers in a single view. No more side-by-side browser tabs or manual data entry into Excel.
                            </p>
                            <ul className="space-y-4">
                                <li className="flex items-center gap-3 text-sm font-medium text-charcoal/80">
                                    <CheckCircle2 size={18} style={{ color: '#BAE3A1' }} /> Compare step therapy and prior auth rules across payers
                                </li>
                                <li className="flex items-center gap-3 text-sm font-medium text-charcoal/80">
                                    <CheckCircle2 size={18} style={{ color: '#BAE3A1' }} /> Filter by drug, payer, or policy type in seconds
                                </li>
                            </ul>
                        </div>
                        <div className="w-full justify-self-end rounded-2xl aspect-[1812/1204] bg-[#f7f4ef] p-3 md:p-4">
                            <div className="h-full w-full overflow-hidden rounded-[1.45rem] border-2 border-charcoal/90 bg-white shadow-[0_24px_50px_rgba(28,28,26,0.12)]">
                                <img
                                    src="/comparsion.webp"
                                    alt="Cross-payer comparison dashboard preview"
                                    className="h-full w-full object-contain object-center"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Section 2 */}
                    <div className="grid items-center gap-10 md:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] md:gap-12 lg:gap-16">
                        <div className="order-2 md:order-1 w-full rounded-2xl aspect-[1792/1208] bg-[#4a807a] p-4 md:p-6">
                            <div className="h-full w-full overflow-hidden rounded-[1.45rem] border-2 border-charcoal/25 bg-white shadow-[0_24px_50px_rgba(28,28,26,0.16)]">
                                <img
                                    src="/approval_path.webp"
                                    alt="Approval path generator dashboard preview"
                                    className="h-full w-full object-contain object-center"
                                />
                            </div>
                        </div>
                        <div className="order-1 md:order-2 max-w-lg">
                            <SectionLabel className="bg-[#FFDBD3] text-[#4D261A]">Clinical Insight</SectionLabel>
                            <h2 className="font-serif text-5xl md:text-6xl font-medium mb-6 md:mb-8 leading-tight">
                                The Approval <br /> Path Generator
                            </h2>
                            <p className="text-xl text-charcoal/60 leading-relaxed mb-8 md:mb-10">
                                Input a patient profile and see exactly which payers will approve the therapy—and what clinical evidence is required to secure the prior authorization.
                            </p>
                            <Button variant="primary" className="bg-[#4d261a]" href="/auth/login?returnTo=/approval-path">Explore Clinical Paths</Button>
                        </div>
                    </div>

                    {/* Section 3 */}
                    <div className="grid items-center gap-10 md:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] md:gap-12 lg:gap-16">
                        <div className="order-1 md:order-2 w-full justify-self-end rounded-2xl bg-[#F5F2ED] p-4 md:p-6">
                            <div className="mx-auto w-full max-w-[34rem] overflow-hidden rounded-[1.45rem] border-2 border-charcoal/85 bg-white shadow-[0_24px_50px_rgba(28,28,26,0.12)]">
                                <img
                                    src="/ai_screenshot.webp"
                                    alt="AI search cited answers dashboard preview"
                                    className="h-auto w-full object-contain"
                                />
                            </div>
                        </div>
                        <div className="order-2 md:order-1 max-w-lg">
                            <SectionLabel className="bg-[#F3EFE0] text-[#8B7E66]">AI Search</SectionLabel>
                            <h2 className="font-serif text-5xl md:text-6xl font-medium mb-6 md:mb-8 leading-tight">
                                Ask anything. <br /> Get cited answers.
                            </h2>
                            <p className="text-xl text-charcoal/60 leading-relaxed mb-8 md:mb-10">
                                Stop <code className="text-sm bg-surface-low px-1 rounded">Ctrl+F</code>ing through 30-page PDFs. Ask plain English questions like "What are the step therapy rules for Infliximab under Aetna?" and get instant, accurate answers with direct citations back to the source document.
                            </p>
                        </div>
                    </div>

                </div>
            </section>

            <Separator />

            {/* Methodology Section */}
            <section className="bg-surface-low/50 px-5 py-24 md:px-6 md:py-28">
                <div id="methodology" className="max-w-7xl mx-auto scroll-mt-38">
                    <div className="rounded-[2rem] border border-charcoal/8 bg-white p-6 md:p-8 lg:p-10 editorial-shadow">
                        <div className="grid gap-6 border-b border-charcoal/8 pb-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.3fr)_auto] lg:items-start">
                            <div className="max-w-md">
                                <SectionLabel className="mb-3 bg-charcoal/6 text-charcoal/60">Hackathon Build</SectionLabel>
                                <h2 className="font-serif text-4xl leading-tight font-medium md:text-5xl">
                                    Built fast. Designed to be real.
                                </h2>
                            </div>
                            <p className="max-w-3xl text-lg md:text-xl leading-relaxed text-charcoal/75">
                                PolicyDiff is a hackathon prototype focused on one clear problem: turning dense medical policy PDFs into structured answers, side-by-side comparisons, and actionable approval guidance through one usable workflow.
                            </p>
                            <div className="inline-flex h-fit rounded-full bg-terracotta/8 px-4 py-2 text-[11px] font-bold uppercase tracking-[0.16em] text-terracotta">
                                Hackathon-Ready
                            </div>
                        </div>

                        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                            <div className="rounded-2xl bg-surface-low/80 p-5 md:p-6">
                                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-charcoal/45">Core Scope</p>
                                <div className="mt-4 flex flex-wrap gap-2">
                                    <span className="rounded-full bg-white px-3 py-1.5 text-sm font-medium text-charcoal/75">PDF ingestion</span>
                                    <span className="rounded-full bg-white px-3 py-1.5 text-sm font-medium text-charcoal/75">Structured extraction</span>
                                    <span className="rounded-full bg-white px-3 py-1.5 text-sm font-medium text-charcoal/75">Payer comparison</span>
                                    <span className="rounded-full bg-white px-3 py-1.5 text-sm font-medium text-charcoal/75">Approval-path logic</span>
                                    <span className="rounded-full bg-white px-3 py-1.5 text-sm font-medium text-charcoal/75">Cited AI search</span>
                                </div>
                            </div>
                            <div className="rounded-2xl border border-charcoal/8 p-5 md:p-6">
                                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-charcoal/45">Demo Goal</p>
                                <div className="mt-4 grid gap-3 text-sm leading-relaxed text-charcoal/65">
                                    <p>Show a product that feels focused, opinionated, and immediately useful.</p>
                                    <p>Prove that policy research can move from PDF scanning to structured decisions.</p>
                                    <p>Make the system legible enough for judges, teammates, and future users.</p>
                                </div>
                            </div>
                        </div>

                        <div className="mt-6 grid gap-4 md:grid-cols-3">
                            <div className="rounded-2xl border border-charcoal/8 bg-white px-5 py-5">
                                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-charcoal/45">01 Input</p>
                                <p className="mt-3 font-serif text-[1.9rem] leading-none">PDFs</p>
                                <p className="mt-3 text-sm leading-relaxed text-charcoal/60">Raw payer policies become machine-readable workflows.</p>
                            </div>
                            <div className="rounded-2xl border border-charcoal/8 bg-white px-5 py-5">
                                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-charcoal/45">02 Engine</p>
                                <p className="mt-3 font-serif text-[1.9rem] leading-none">AI + Rules</p>
                                <p className="mt-3 text-sm leading-relaxed text-charcoal/60">Extraction logic turns policy language into usable signals.</p>
                            </div>
                            <div className="rounded-2xl border border-charcoal/8 bg-white px-5 py-5">
                                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-charcoal/45">03 Outcome</p>
                                <p className="mt-3 font-serif text-[1.9rem] leading-none">Faster Reads</p>
                                <p className="mt-3 text-sm leading-relaxed text-charcoal/60">Less manual scanning, quicker answers, and clearer payer-to-payer visibility.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-charcoal/5 px-5 py-16 md:px-6 md:py-[4.5rem]">
                <div className="max-w-7xl mx-auto flex flex-col justify-between gap-10 md:flex-row md:items-end md:gap-12">
                    <div className="max-w-xs">
                        <span className="font-serif text-xl italic font-medium text-terracotta mb-4 block">PolicyDiff</span>
                        <p className="text-xs text-charcoal/40 leading-relaxed">
                            © 2026 PolicyDiff. Curated Healthcare Policy Intelligence.
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-x-12 gap-y-4 text-[10px] uppercase tracking-widest font-bold text-charcoal/60">
                        <a href="#" className="hover:text-terracotta transition-colors">Privacy Policy</a>
                        <a href="#" className="hover:text-terracotta transition-colors">Terms of Service</a>
                        <a href="#" className="hover:text-terracotta transition-colors">Security</a>
                        <a href="#" className="hover:text-terracotta transition-colors">Contact</a>
                    </div>
                </div>
            </footer>
        </div>
    );
}
