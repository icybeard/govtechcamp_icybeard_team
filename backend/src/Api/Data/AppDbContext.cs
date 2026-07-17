using Microsoft.EntityFrameworkCore;

namespace GovTech.Api.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<User> Users => Set<User>();
    public DbSet<Region> Regions => Set<Region>();
    public DbSet<RegionMetric> RegionMetrics => Set<RegionMetric>();
    public DbSet<Settlement> Settlements => Set<Settlement>();
    public DbSet<SettlementMetric> SettlementMetrics => Set<SettlementMetric>();
    public DbSet<PreventiveMeasure> PreventiveMeasures => Set<PreventiveMeasure>();
    public DbSet<DatasetFile> DatasetFiles => Set<DatasetFile>();

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

        modelBuilder.Entity<Settlement>(e =>
        {
            e.HasIndex(s => new { s.RegionId, s.Name });
            e.Property(s => s.Name).HasMaxLength(300);
            e.Property(s => s.KatoCode).HasMaxLength(20);
            e.HasOne(s => s.Region).WithMany().HasForeignKey(s => s.RegionId);
        });

        modelBuilder.Entity<SettlementMetric>(e =>
        {
            e.HasIndex(m => new { m.SettlementId, m.Module, m.MetricKey, m.Period }).IsUnique();
            e.Property(m => m.Module).HasMaxLength(50);
            e.Property(m => m.MetricKey).HasMaxLength(100);
            e.Property(m => m.Period).HasMaxLength(20);
            e.HasOne(m => m.Settlement).WithMany(s => s.Metrics).HasForeignKey(m => m.SettlementId);
        });

        modelBuilder.Entity<PreventiveMeasure>(e =>
        {
            e.HasIndex(m => new { m.Module, m.Status });
            e.HasIndex(m => m.SettlementId);
            e.HasIndex(m => new { m.Module, m.DistrictId }); // дедуп district-мер при генерации
            e.Property(m => m.Module).HasMaxLength(50);
            e.Property(m => m.Title).HasMaxLength(300);
            e.Property(m => m.Status).HasMaxLength(20);
            e.Property(m => m.DecidedByName).HasMaxLength(200);
            e.Property(m => m.DistrictId).HasMaxLength(100);
            e.Property(m => m.DistrictName).HasMaxLength(300);
            e.HasOne(m => m.Settlement).WithMany().HasForeignKey(m => m.SettlementId);
        });

        modelBuilder.Entity<DatasetFile>(e =>
        {
            e.HasIndex(d => d.UploadedAt);
            e.Property(d => d.FileName).HasMaxLength(300);
            e.Property(d => d.Kind).HasMaxLength(50);
            e.Property(d => d.Period).HasMaxLength(20);
            e.Property(d => d.Note).HasMaxLength(1000);
            e.Property(d => d.StoredPath).HasMaxLength(500);
            e.Property(d => d.UploadedByName).HasMaxLength(200);
        });
    }
}
