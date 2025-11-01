// src/components/Dashboard.tsx (Updated with Tabs)
'use client';

import { useState, useEffect } from 'react';
import { collection, query, where, onSnapshot, orderBy } from 'firebase/firestore';
import { db } from '@/lib/firebase';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface HelpRequest {
    id: string;
    originalQuery: string;
    status: string;
    createdAt: {
        seconds: number;
        nanoseconds: number;
    };
    conversationHistory: Array<{ role: string; content: string }>;
    supervisorResponse?: string; // History me dikhane ke liye
}

interface KnowledgeBaseEntry {
    id: string;
    question: string;
    answer: string;
    createdAt?: {
        seconds: number;
        nanoseconds: number;
    };
    sourceRequestId?: string;
}

// Jawab dene wala form
function ResolveForm({ requestId }: { requestId: string }) {
    const [answer, setAnswer] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleResolve = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!answer.trim()) {
            alert('Please provide an answer.');
            return;
        }
        setIsSubmitting(true);
        try {
            const response = await fetch(`http://127.0.0.1:8000/api/help-requests/${requestId}/resolve`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answer }),
            });
            if (!response.ok) throw new Error('Failed to resolve request');
            console.log(`Request ${requestId} resolved!`);
        } catch (error) {
            console.error(error);
            alert('Could not resolve the request.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleResolve} className="w-full flex flex-col gap-2">
            <Textarea
                placeholder="Type your answer for the user here..."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={isSubmitting}
            />
            <Button type="submit" disabled={isSubmitting} className="self-end">
                {isSubmitting? 'Submitting...' : 'Submit Answer'}
            </Button>
        </form>
    );
}

// Pending requests dikhane wala component
function PendingRequests() {
    const [requests, setRequests] = useState<HelpRequest[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const q = query(
            collection(db, 'help_requests'),
            where('status', '==', 'pending'),
            orderBy('createdAt', 'desc')
        );
        const unsubscribe = onSnapshot(q, (snapshot) => {
            const reqs = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as HelpRequest));
            setRequests(reqs);
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    if (loading) return <p>Loading pending requests...</p>;

    return (
        <div className="grid gap-4">
            {requests.length > 0? (
                requests.map((req) => (
                    <Card key={req.id}>
                        <CardHeader>
                            <CardTitle>Query: {req.originalQuery}</CardTitle>
                            <CardDescription>Received: {new Date(req.createdAt.seconds * 1000).toLocaleString()}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {/* Conversation History... */}
                        </CardContent>
                        <CardFooter>
                            <ResolveForm requestId={req.id} />
                        </CardFooter>
                    </Card>
                ))
            ) : (
                <p>No pending requests found. Great job!</p>
            )}
        </div>
    );
}

// History (resolved) requests dikhane wala component
function HistoryRequests() {
    const [requests, setRequests] = useState<HelpRequest[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const q = query(
            collection(db, 'help_requests'),
            where('status', '==', 'resolved'), // Sirf resolved wale
            orderBy('createdAt', 'desc')
        );
        const unsubscribe = onSnapshot(q, (snapshot) => {
            const reqs = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as HelpRequest));
            setRequests(reqs);
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    if (loading) return <p>Loading history...</p>;

    return (
        <div className="grid gap-4">
            {requests.length > 0? (
                requests.map((req) => (
                    <Card key={req.id} className="bg-slate-50">
                        <CardHeader>
                            <CardTitle>Query: {req.originalQuery}</CardTitle>
                            <CardDescription>Resolved on: {new Date(req.createdAt.seconds * 1000).toLocaleString()}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <p className="font-semibold">Supervisor's Answer:</p>
                            <p className="p-2 bg-white rounded-md">{req.supervisorResponse}</p>
                        </CardContent>
                    </Card>
                ))
            ) : (
                <p>No resolved requests yet.</p>
            )}
        </div>
    );
}

function LearnedAnswers() {
    const [entries, setEntries] = useState<KnowledgeBaseEntry[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const q = query(
            collection(db, 'knowledge_base'),
            orderBy('createdAt', 'desc')
        );
        const unsubscribe = onSnapshot(q, (snapshot) => {
            const docs = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as KnowledgeBaseEntry));
            setEntries(docs);
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    if (loading) return <p>Loading learned answers...</p>;

    return (
        <div className="grid gap-4">
            {entries.length > 0 ? (
                entries.map((entry) => (
                    <Card key={entry.id} className="bg-emerald-50">
                        <CardHeader>
                            <CardTitle>Learned Answer</CardTitle>
                            {entry.createdAt && (
                                <CardDescription>
                                    Learned on: {new Date(entry.createdAt.seconds * 1000).toLocaleString()}
                                </CardDescription>
                            )}
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <div>
                                <p className="font-semibold">Question</p>
                                <p className="rounded-md bg-white p-2">{entry.question}</p>
                            </div>
                            <div>
                                <p className="font-semibold">Answer</p>
                                <p className="rounded-md bg-white p-2">{entry.answer}</p>
                            </div>
                        </CardContent>
                        {entry.sourceRequestId && (
                            <CardFooter>
                                <Badge variant="secondary" className="ml-auto">Request ID: {entry.sourceRequestId}</Badge>
                            </CardFooter>
                        )}
                    </Card>
                ))
            ) : (
                <p>The agent has not learned any new answers yet.</p>
            )}
        </div>
    );
}

// Main Dashboard component
export default function Dashboard() {
    return (
        <div className="p-8 max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold mb-6">Supervisor Dashboard</h1>
            <Tabs defaultValue="pending" className="w-full">
                <TabsList>
                    <TabsTrigger value="pending">Pending</TabsTrigger>
                    <TabsTrigger value="history">History</TabsTrigger>
                    <TabsTrigger value="knowledge">Learned Answers</TabsTrigger>
                </TabsList>
                <TabsContent value="pending" className="mt-4">
                    <PendingRequests />
                </TabsContent>
                <TabsContent value="history" className="mt-4">
                    <HistoryRequests />
                </TabsContent>
                <TabsContent value="knowledge" className="mt-4">
                    <LearnedAnswers />
                </TabsContent>
            </Tabs>
        </div>
    );
}