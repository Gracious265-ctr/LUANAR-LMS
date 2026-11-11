"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CampusForm } from "./campus-form";

export function CampusCreateDialog() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary">
          <Plus className="h-4 w-4" />
          New campus
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New campus</DialogTitle>
          <DialogDescription>
            A campus is where an academic team sits and what scopes its
            campus-wide approvers.
          </DialogDescription>
        </DialogHeader>
        <CampusForm
          onSaved={() => {
            setOpen(false);
            router.refresh();
          }}
          returnTo=""
        />
      </DialogContent>
    </Dialog>
  );
}
