using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<User> Users => Set<User>();
    public DbSet<Region> Regions => Set<Region>();
    public DbSet<RegionMetric> RegionMetrics => Set<RegionMetric>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<User>(e =>
        {
            e.HasIndex(u => u.Email).IsUnique();
            e.Property(u => u.Email).HasMaxLength(320);
            e.Property(u => u.DisplayName).HasMaxLength(200);
            e.Property(u => u.Role).HasMaxLength(50);
        });

        modelBuilder.Entity<Region>(e =>
        {
            e.HasIndex(r => r.IsoCode).IsUnique();
            e.Property(r => r.IsoCode).HasMaxLength(10);
            e.Property(r => r.NameEn).HasMaxLength(200);
            e.Property(r => r.NameRu).HasMaxLength(200);
        });

        modelBuilder.Entity<RegionMetric>(e =>
        {
            e.HasIndex(m => new { m.RegionId, m.Module, m.MetricKey, m.Period }).IsUnique();
            e.Property(m => m.Module).HasMaxLength(50);
            e.Property(m => m.MetricKey).HasMaxLength(100);
            e.Property(m => m.Period).HasMaxLength(20);
            e.HasOne(m => m.Region).WithMany(r => r.Metrics).HasForeignKey(m => m.RegionId);
        });
    }
}
